"""
PIDME Backend — FastAPI application
Ball Bearings catalog from motion.com + image matching engine
"""

import asyncio
import logging
import os
from pathlib import Path
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, BackgroundTasks, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlmodel import select, func
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from models import Product, ImageCandidate, SQLModel
from seed_data import SEED_PRODUCTS
from image_finder import search_product_images

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

DATABASE_URL = "sqlite+aiosqlite:///./pidme.db"
engine = create_async_engine(DATABASE_URL, echo=False)
SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


# ── Lifespan: DB init + seed ──────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    await seed_database()
    yield
    await engine.dispose()


async def seed_database():
    """Insert seed products and pre-discovered image candidates."""
    from seed_candidates import SEED_CANDIDATES
    async with SessionLocal() as session:
        count = (await session.exec(select(func.count(Product.id)))).one()
        if count > 0:
            return
        logger.info(f"Seeding {len(SEED_PRODUCTS)} products...")
        for p_data in SEED_PRODUCTS:
            session.add(Product(**p_data))
        await session.commit()

        logger.info("Seeding pre-discovered image candidates...")
        all_products = (await session.exec(select(Product))).all()
        sku_to_id = {p.motion_sku: p.id for p in all_products}

        for motion_sku, candidates in SEED_CANDIDATES.items():
            product_id = sku_to_id.get(motion_sku)
            if not product_id:
                continue
            best_score = 0.0
            best_url = ""
            for c in candidates:
                session.add(ImageCandidate(product_id=product_id, **c))
                if c["composite_score"] > best_score:
                    best_score = c["composite_score"]
                    best_url = c["image_url"]
            product = await session.get(Product, product_id)
            if product and best_url:
                product.image_status = "approved" if best_score >= 0.75 else "matched"
                product.approved_image_url = best_url
                product.approved_image_score = best_score
                session.add(product)

        await session.commit()
        logger.info("Seed complete.")


app = FastAPI(
    title="PIDME — Product Image Discovery & Matching",
    description="Ball bearings catalog from motion.com with automated image matching",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Helpers ───────────────────────────────────────────────────────────────

async def get_session():
    async with SessionLocal() as session:
        yield session


# ── Products endpoints ────────────────────────────────────────────────────

@app.get("/api/products")
async def list_products(
    search: Optional[str] = Query(None, description="Search by SKU, part number, or manufacturer"),
    image_status: Optional[str] = Query(None, description="Filter by image_status"),
    product_type: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
):
    async with SessionLocal() as session:
        query = select(Product)
        if search:
            s = f"%{search.lower()}%"
            query = query.where(
                (func.lower(Product.mfr_name).like(s)) |
                (func.lower(Product.mfr_part_number).like(s)) |
                (func.lower(Product.motion_sku).like(s)) |
                (func.lower(Product.description).like(s))
            )
        if image_status:
            query = query.where(Product.image_status == image_status)
        if product_type:
            query = query.where(Product.product_type == product_type)

        total = (await session.exec(select(func.count()).select_from(query.subquery()))).one()
        products = (await session.exec(
            query.offset((page - 1) * per_page).limit(per_page)
        )).all()

        return {
            "total": total,
            "page": page,
            "per_page": per_page,
            "pages": (total + per_page - 1) // per_page,
            "products": [p.model_dump() for p in products],
        }


@app.get("/api/products/{product_id}")
async def get_product(product_id: int):
    async with SessionLocal() as session:
        product = await session.get(Product, product_id)
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")

        candidates = (await session.exec(
            select(ImageCandidate)
            .where(ImageCandidate.product_id == product_id)
            .order_by(ImageCandidate.composite_score.desc())
        )).all()

        return {
            "product": product.model_dump(),
            "candidates": [c.model_dump() for c in candidates],
        }


@app.get("/api/stats")
async def get_stats():
    async with SessionLocal() as session:
        total = (await session.exec(select(func.count(Product.id)))).one()

        status_counts = {}
        for status in ["no_image", "pending", "matched", "approved", "rejected"]:
            cnt = (await session.exec(
                select(func.count(Product.id)).where(Product.image_status == status)
            )).one()
            status_counts[status] = cnt

        total_candidates = (await session.exec(
            select(func.count(ImageCandidate.id))
        )).one()

        high_conf = (await session.exec(
            select(func.count(ImageCandidate.id))
            .where(ImageCandidate.confidence_tier == "high")
        )).one()

        return {
            "total_products": total,
            "coverage_pct": round((status_counts.get("approved", 0) + status_counts.get("matched", 0)) / max(total, 1) * 100, 1),
            "status_breakdown": status_counts,
            "total_candidates_discovered": total_candidates,
            "high_confidence_candidates": high_conf,
        }


@app.get("/api/product_types")
async def get_product_types():
    async with SessionLocal() as session:
        types = (await session.exec(
            select(Product.product_type).distinct()
        )).all()
        return [t for t in types if t]


# ── Image matching endpoints ──────────────────────────────────────────────

@app.post("/api/match/batch")
async def match_all_products(background_tasks: BackgroundTasks):
    """Trigger image matching for all products without approved images."""
    async with SessionLocal() as session:
        products = (await session.exec(
            select(Product).where(Product.image_status.in_(["no_image", "rejected"]))
        )).all()
        ids = [p.id for p in products]
        for p in products:
            p.image_status = "pending"
        session.add_all(products)
        await session.commit()

    background_tasks.add_task(_run_batch_matching, ids)
    return {"status": "started", "product_count": len(ids)}


@app.post("/api/match/{product_id}")
async def match_product_images(product_id: int, background_tasks: BackgroundTasks):
    """
    Trigger image discovery and scoring for a single product.
    Returns immediately; matching runs in the background.
    """
    async with SessionLocal() as session:
        product = await session.get(Product, product_id)
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")
        if product.image_status == "pending":
            return {"status": "already_running", "product_id": product_id}
        product.image_status = "pending"
        session.add(product)
        await session.commit()

    background_tasks.add_task(_run_matching, product_id)
    return {"status": "started", "product_id": product_id}


async def _run_matching(product_id: int):
    """Background task: find and score images for one product."""
    async with SessionLocal() as session:
        product = await session.get(Product, product_id)
        if not product:
            return

        logger.info(f"Starting image match for {product.mfr_name} {product.mfr_part_number}")

        try:
            # Run DuckDuckGo search in thread pool (sync library)
            loop = asyncio.get_event_loop()
            candidates = await loop.run_in_executor(
                None,
                lambda: search_product_images(
                    product.mfr_name,
                    product.mfr_part_number,
                    product.description,
                    max_results=6,
                ),
            )

            # Delete stale candidates for this product
            existing = (await session.exec(
                select(ImageCandidate).where(ImageCandidate.product_id == product_id)
            )).all()
            for c in existing:
                await session.delete(c)

            if not candidates:
                product.image_status = "no_image"
                session.add(product)
                await session.commit()
                return

            # Insert new candidates
            best = None
            for c in candidates:
                db_candidate = ImageCandidate(
                    product_id=product_id,
                    image_url=c.image_url,
                    thumbnail_url=c.thumbnail_url,
                    source_domain=c.source_domain,
                    source_query=c.source_query,
                    title=c.title,
                    url_relevance_score=c.url_relevance_score,
                    title_relevance_score=c.title_relevance_score,
                    domain_trust_score=c.domain_trust_score,
                    composite_score=c.composite_score,
                    confidence_tier=c.confidence_tier,
                )
                session.add(db_candidate)
                if best is None or c.composite_score > best.composite_score:
                    best = c

            # Auto-approve high confidence top match
            if best and best.confidence_tier == "high":
                product.image_status = "matched"
                product.approved_image_url = best.image_url
                product.approved_image_score = best.composite_score
            else:
                product.image_status = "matched"
                if best:
                    product.approved_image_url = best.image_url
                    product.approved_image_score = best.composite_score

            session.add(product)
            await session.commit()
            logger.info(
                f"Matched {product.mfr_part_number}: "
                f"best score={best.composite_score if best else 0:.3f} "
                f"tier={best.confidence_tier if best else 'none'}"
            )

        except Exception as e:
            logger.error(f"Matching failed for product {product_id}: {e}")
            product.image_status = "no_image"
            session.add(product)
            await session.commit()


async def _run_batch_matching(product_ids: list[int]):
    """Background task: match images for a list of products with delay between each."""
    for i, pid in enumerate(product_ids):
        logger.info(f"Batch matching [{i+1}/{len(product_ids)}] product_id={pid}")
        await _run_matching(pid)
        await asyncio.sleep(2)  # Polite delay between DuckDuckGo queries


# ── Candidate approval / rejection ───────────────────────────────────────

@app.post("/api/candidates/{candidate_id}/approve")
async def approve_candidate(candidate_id: int):
    async with SessionLocal() as session:
        candidate = await session.get(ImageCandidate, candidate_id)
        if not candidate:
            raise HTTPException(status_code=404, detail="Candidate not found")

        candidate.status = "approved"
        product = await session.get(Product, candidate.product_id)
        if product:
            product.image_status = "approved"
            product.approved_image_url = candidate.image_url
            product.approved_image_score = candidate.composite_score
            session.add(product)
        session.add(candidate)
        await session.commit()
        return {"status": "approved", "image_url": candidate.image_url}


@app.post("/api/candidates/{candidate_id}/reject")
async def reject_candidate(candidate_id: int):
    async with SessionLocal() as session:
        candidate = await session.get(ImageCandidate, candidate_id)
        if not candidate:
            raise HTTPException(status_code=404, detail="Candidate not found")
        candidate.status = "rejected"
        session.add(candidate)
        await session.commit()
        return {"status": "rejected"}


# ── Scraper trigger endpoint ──────────────────────────────────────────────

@app.post("/api/scrape")
async def trigger_scrape(background_tasks: BackgroundTasks, max_products: int = 50):
    """
    Trigger the motion.com Playwright scraper (requires local/residential network).
    In containerized/CI environments, motion.com WAF returns 403.
    """
    background_tasks.add_task(_run_scraper, max_products)
    return {
        "status": "started",
        "note": "Scraper requires unrestricted outbound network access to motion.com",
        "max_products": max_products,
    }


async def _run_scraper(max_products: int):
    from scraper import run_scraper
    logger.info(f"Starting motion.com scraper (max_products={max_products})")
    try:
        products = await run_scraper(max_products)
        async with SessionLocal() as session:
            for p in products:
                existing = (await session.exec(
                    select(Product).where(Product.motion_sku == p.motion_sku)
                )).first()
                if not existing:
                    session.add(Product(**p.__dict__))
            await session.commit()
        logger.info(f"Scraper finished: {len(products)} products saved")
    except Exception as e:
        logger.error(f"Scraper error: {e}")


# ── Image proxy (avoids hotlink blocks from external image hosts) ─────

@app.get("/api/image-proxy")
async def image_proxy(url: str = Query(..., description="External image URL to proxy")):
    import requests as req
    from fastapi.responses import Response, RedirectResponse
    try:
        resp = req.get(url, timeout=8, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "image/*",
        })
        if resp.status_code == 200 and len(resp.content) > 500:
            content_type = resp.headers.get("content-type", "image/jpeg")
            return Response(content=resp.content, media_type=content_type)
    except Exception:
        pass
    return RedirectResponse("https://placehold.co/200x200/1e293b/64748b?text=Bearing")


# ── Serve React frontend ──────────────────────────────────────────────

DIST_DIR = Path(__file__).parent / "dist"

if DIST_DIR.is_dir():
    app.mount("/assets", StaticFiles(directory=DIST_DIR / "assets"), name="static")

    @app.get("/{path:path}")
    async def serve_frontend(path: str):
        return FileResponse(DIST_DIR / "index.html")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
