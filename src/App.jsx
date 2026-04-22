import { useState, useCallback } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import axios from 'axios'

const api = axios.create({ baseURL: '/api' })

const useStats = () => useQuery({ queryKey: ['stats'], queryFn: () => api.get('/stats').then(r => r.data), refetchInterval: 5000 })
const useProducts = (filters) => useQuery({ queryKey: ['products', filters], queryFn: () => api.get('/products', { params: filters }).then(r => r.data), keepPreviousData: true })
const useProduct = (id) => useQuery({ queryKey: ['product', id], queryFn: () => api.get(`/products/${id}`).then(r => r.data), enabled: !!id })
const useProductTypes = () => useQuery({ queryKey: ['product_types'], queryFn: () => api.get('/product_types').then(r => r.data) })

const STATUS_CFG = {
  approved: { label: 'Approved', color: '#10b981', bg: '#052e16' },
  matched:  { label: 'Matched',  color: '#3b82f6', bg: '#0c1a3a' },
  pending:  { label: 'Pending',  color: '#f59e0b', bg: '#2d1b00' },
  no_image: { label: 'No Image', color: '#64748b', bg: '#0f1623' },
  rejected: { label: 'Rejected', color: '#ef4444', bg: '#2d0b0b' },
}
const TIER_CFG = {
  high:   { label: 'HIGH', color: '#10b981', bg: '#052e16' },
  medium: { label: 'MED',  color: '#f59e0b', bg: '#2d1b00' },
  low:    { label: 'LOW',  color: '#ef4444', bg: '#2d0b0b' },
}

const Badge = ({ text, color, bg }) => (
  <span style={{ display:'inline-block', padding:'2px 8px', borderRadius:4, fontSize:11,
    fontWeight:700, letterSpacing:'0.05em', textTransform:'uppercase',
    color, background:bg, border:`1px solid ${color}33` }}>{text}</span>
)

const ScoreBar = ({ label, score, color }) => (
  <div style={{ marginBottom:8 }}>
    <div style={{ display:'flex', justifyContent:'space-between', marginBottom:3 }}>
      <span style={{ fontSize:11, color:'#94a3b8' }}>{label}</span>
      <span style={{ fontSize:11, color, fontWeight:700 }}>{(score*100).toFixed(0)}%</span>
    </div>
    <div style={{ height:4, background:'#1e293b', borderRadius:2, overflow:'hidden' }}>
      <div style={{ height:'100%', width:`${score*100}%`, background:color, borderRadius:2, transition:'width 0.4s ease' }} />
    </div>
  </div>
)

const Spinner = () => (
  <div style={{ display:'flex', alignItems:'center', justifyContent:'center', padding:40 }}>
    <div style={{ width:32, height:32, border:'3px solid #1e293b', borderTopColor:'#3b82f6',
      borderRadius:'50%', animation:'spin 0.8s linear infinite' }} />
    <style>{`@keyframes spin{to{transform:rotate(360deg)}}`}</style>
  </div>
)

const StatsBar = () => {
  const { data } = useStats()
  if (!data) return null
  return (
    <div style={{ display:'grid', gridTemplateColumns:'repeat(4,1fr)', gap:12, marginBottom:24 }}>
      {[
        { label:'Total Products',    value:data.total_products,              color:'#3b82f6' },
        { label:'Image Coverage',    value:`${data.coverage_pct}%`,          color:'#10b981' },
        { label:'High Confidence',   value:data.high_confidence_candidates,  color:'#a855f7' },
        { label:'Candidates Found',  value:data.total_candidates_discovered, color:'#f59e0b' },
      ].map(c => (
        <div key={c.label} style={{ background:'#111827', border:'1px solid #1e293b',
          borderTop:`3px solid ${c.color}`, padding:'16px 20px', borderRadius:8 }}>
          <div style={{ fontSize:28, fontWeight:900, color:c.color, lineHeight:1 }}>{c.value}</div>
          <div style={{ fontSize:11, color:'#64748b', marginTop:6, letterSpacing:'0.06em', textTransform:'uppercase' }}>{c.label}</div>
        </div>
      ))}
    </div>
  )
}

const StatusBreakdown = () => {
  const { data } = useStats()
  if (!data?.status_breakdown) return null
  const bd = data.status_breakdown
  const entries = Object.entries(STATUS_CFG).map(([k, cfg]) => ({ key:k, cfg, count:bd[k]||0 }))
  return (
    <div style={{ background:'#111827', border:'1px solid #1e293b', borderRadius:8, padding:'16px 20px', marginBottom:24 }}>
      <div style={{ fontSize:11, letterSpacing:'0.1em', color:'#475569', textTransform:'uppercase', marginBottom:14 }}>Image Status Breakdown</div>
      <div style={{ height:8, borderRadius:4, overflow:'hidden', display:'flex', marginBottom:12 }}>
        {entries.map(e => e.count > 0 && <div key={e.key} style={{ flex:e.count, background:e.cfg.color }} />)}
      </div>
      <div style={{ display:'flex', gap:20, flexWrap:'wrap' }}>
        {entries.map(e => (
          <div key={e.key} style={{ display:'flex', alignItems:'center', gap:6 }}>
            <div style={{ width:10, height:10, borderRadius:2, background:e.cfg.color }} />
            <span style={{ fontSize:12, color:'#94a3b8' }}>{e.cfg.label}: </span>
            <span style={{ fontSize:12, fontWeight:700, color:e.cfg.color }}>{e.count}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

const CandidatesPanel = ({ productId, onClose }) => {
  const { data, isLoading } = useProduct(productId)
  const queryClient = useQueryClient()
  const inv = () => { queryClient.invalidateQueries(['product',productId]); queryClient.invalidateQueries(['products']); queryClient.invalidateQueries(['stats']) }
  const approveMut = useMutation({ mutationFn: cid => api.post(`/candidates/${cid}/approve`), onSuccess: inv })
  const rejectMut  = useMutation({ mutationFn: cid => api.post(`/candidates/${cid}/reject`), onSuccess: () => queryClient.invalidateQueries(['product',productId]) })
  const matchMut   = useMutation({ mutationFn: pid => api.post(`/match/${pid}`), onSuccess: inv })

  if (isLoading) return (
    <div style={{ position:'fixed', inset:0, background:'#000a', display:'flex', alignItems:'center', justifyContent:'center', zIndex:100 }}><Spinner /></div>
  )
  const { product, candidates } = data || {}

  return (
    <div style={{ position:'fixed', inset:0, background:'#000c', zIndex:100, display:'flex', alignItems:'flex-end', justifyContent:'flex-end' }} onClick={onClose}>
      <div style={{ width:680, height:'100vh', background:'#0f1623', border:'1px solid #1e293b', borderRight:'none', overflow:'auto', padding:24 }} onClick={e => e.stopPropagation()}>

        <div style={{ display:'flex', justifyContent:'space-between', alignItems:'flex-start', marginBottom:20 }}>
          <div>
            <div style={{ fontSize:11, color:'#475569', letterSpacing:'0.08em', textTransform:'uppercase' }}>{product?.mfr_name}</div>
            <div style={{ fontSize:18, fontWeight:700, color:'#f0f9ff', marginTop:2 }}>{product?.mfr_part_number}</div>
            <div style={{ fontSize:12, color:'#94a3b8', marginTop:4 }}>{product?.description}</div>
          </div>
          <button onClick={onClose} style={{ background:'transparent', border:'1px solid #1e293b', color:'#64748b', padding:'6px 12px', borderRadius:6, fontSize:13 }}>✕ Close</button>
        </div>

        <div style={{ background:'#111827', border:'1px solid #1e293b', borderRadius:8, padding:16, marginBottom:20, display:'grid', gridTemplateColumns:'1fr 1fr', gap:'6px 20px' }}>
          {[['Bore',product?.bore_diameter],['OD',product?.outside_diameter],['Width',product?.overall_width],['Closure',product?.closure_type],['Material',product?.bearing_material],['Max RPM',product?.max_rpm],['Dyn Load',product?.radial_dynamic_load],['Precision',product?.precision_rating]].filter(([,v])=>v).map(([l,v])=>(
            <div key={l} style={{ display:'flex', justifyContent:'space-between' }}>
              <span style={{ fontSize:11, color:'#475569' }}>{l}</span>
              <span style={{ fontSize:11, color:'#94a3b8', fontWeight:600 }}>{v}</span>
            </div>
          ))}
        </div>

        <div style={{ display:'flex', gap:8, marginBottom:20, alignItems:'center' }}>
          <button onClick={() => matchMut.mutate(productId)} disabled={matchMut.isPending || product?.image_status==='pending'}
            style={{ background:'#1d4ed8', color:'#fff', border:'none', padding:'8px 16px', borderRadius:6, fontSize:12, fontWeight:600, opacity:matchMut.isPending?0.6:1 }}>
            {matchMut.isPending ? '⏳ Searching...' : '🔍 Search New Images'}
          </button>
          <div style={{ fontSize:11, color:'#475569' }}>
            {product?.image_status==='pending' ? '⏳ Matching in progress...' : `${candidates?.length||0} candidates`}
          </div>
        </div>

        {(!candidates||candidates.length===0) ? (
          <div style={{ textAlign:'center', padding:40, color:'#475569', fontSize:13 }}>No candidates yet. Click "Search New Images".</div>
        ) : candidates.map((c,i) => {
          const tc = TIER_CFG[c.confidence_tier]||TIER_CFG.low
          return (
            <div key={c.id} style={{ background:'#111827', border:`1px solid ${i===0?'#1d4ed8':'#1e293b'}`, borderRadius:8, overflow:'hidden', marginBottom:12, boxShadow:i===0?'0 0 0 1px #1d4ed8':'none' }}>
              {i===0 && <div style={{ background:'#0c1a3a', padding:'4px 12px', fontSize:10, color:'#60a5fa', letterSpacing:'0.1em', fontWeight:700 }}>⭐ BEST MATCH</div>}
              <div style={{ display:'flex' }}>
                <div style={{ width:140, flexShrink:0, background:'#0a0e1a', display:'flex', alignItems:'center', justifyContent:'center', minHeight:120 }}>
                  <img src={c.thumbnail_url||c.image_url} alt={c.title} style={{ maxWidth:130, maxHeight:130, objectFit:'contain' }}
                    onError={e=>{ e.target.style.display='none' }} />
                </div>
                <div style={{ flex:1, padding:14 }}>
                  <div style={{ display:'flex', justifyContent:'space-between', alignItems:'flex-start', marginBottom:10 }}>
                    <div>
                      <span style={{ display:'inline-block', padding:'2px 7px', borderRadius:4, fontSize:10, fontWeight:800, color:tc.color, background:tc.bg, border:`1px solid ${tc.color}44`, marginRight:6 }}>{tc.label}</span>
                      <span style={{ fontSize:18, fontWeight:900, color:tc.color }}>{(c.composite_score*100).toFixed(0)}</span>
                      <span style={{ fontSize:12, color:'#475569' }}>/100</span>
                    </div>
                    <div style={{ display:'flex', gap:6 }}>
                      {c.status!=='approved' && <button onClick={()=>approveMut.mutate(c.id)} style={{ background:'#052e16', color:'#10b981', border:'1px solid #10b98133', padding:'4px 10px', borderRadius:5, fontSize:11, fontWeight:600 }}>✓ Approve</button>}
                      {c.status==='approved' && <span style={{ fontSize:11, color:'#10b981', fontWeight:700 }}>✓ Approved</span>}
                      {c.status!=='rejected'&&c.status!=='approved' && <button onClick={()=>rejectMut.mutate(c.id)} style={{ background:'#2d0b0b', color:'#ef4444', border:'1px solid #ef444433', padding:'4px 10px', borderRadius:5, fontSize:11, fontWeight:600 }}>✗ Reject</button>}
                    </div>
                  </div>
                  <ScoreBar label="Title Relevance" score={c.title_relevance_score} color="#3b82f6" />
                  <ScoreBar label="URL Relevance"   score={c.url_relevance_score}   color="#a855f7" />
                  <ScoreBar label="Domain Trust"    score={c.domain_trust_score}    color="#10b981" />
                  <div style={{ marginTop:8, fontSize:10, color:'#475569' }}>↗ {c.source_domain}</div>
                  {c.title && <div style={{ fontSize:11, color:'#64748b', marginTop:4, fontStyle:'italic' }}>"{c.title.slice(0,80)}"</div>}
                </div>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

const ProductRow = ({ product, onSelect, isSelected }) => {
  const sc = STATUS_CFG[product.image_status]||STATUS_CFG.no_image
  return (
    <tr style={{ borderBottom:'1px solid #1e293b', background:isSelected?'#0c1a3a':'transparent', cursor:'pointer', transition:'background 0.1s' }}
      onClick={()=>onSelect(product.id)}
      onMouseEnter={e=>{ if(!isSelected) e.currentTarget.style.background='#111827' }}
      onMouseLeave={e=>{ if(!isSelected) e.currentTarget.style.background=isSelected?'#0c1a3a':'transparent' }}>
      <td style={{ padding:'10px 16px', width:72 }}>
        {product.approved_image_url ? (
          <div style={{ width:52, height:52, background:'#0a0e1a', borderRadius:6, display:'flex', alignItems:'center', justifyContent:'center', overflow:'hidden', border:'1px solid #1e293b' }}>
            <img src={product.approved_image_url} alt="" style={{ maxWidth:50, maxHeight:50, objectFit:'contain' }} onError={e=>{e.target.parentElement.innerHTML='<span style="font-size:22px;opacity:0.3">⚙</span>'}} />
          </div>
        ) : (
          <div style={{ width:52, height:52, background:'#111827', borderRadius:6, display:'flex', alignItems:'center', justifyContent:'center', border:'1px dashed #1e293b', color:'#475569', fontSize:22 }}>⚙</div>
        )}
      </td>
      <td style={{ padding:'10px 8px' }}>
        <div style={{ fontSize:11, fontFamily:'monospace', color:'#60a5fa', fontWeight:600 }}>{product.motion_sku}</div>
      </td>
      <td style={{ padding:'10px 8px' }}>
        <div style={{ fontSize:13, fontWeight:600, color:'#e2e8f0' }}>{product.mfr_name}</div>
        <div style={{ fontSize:11, color:'#94a3b8', marginTop:2 }}>{product.mfr_part_number}</div>
      </td>
      <td style={{ padding:'10px 8px', maxWidth:220 }}>
        <div style={{ fontSize:12, color:'#94a3b8', whiteSpace:'nowrap', overflow:'hidden', textOverflow:'ellipsis' }}>{product.description}</div>
        <div style={{ fontSize:11, color:'#475569', marginTop:2 }}>{product.product_type}</div>
      </td>
      <td style={{ padding:'10px 8px' }}>
        {product.bore_diameter && <div style={{ fontSize:11, color:'#94a3b8' }}><span style={{ color:'#475569' }}>Bore: </span>{product.bore_diameter}</div>}
        {product.outside_diameter && <div style={{ fontSize:11, color:'#94a3b8' }}><span style={{ color:'#475569' }}>OD: </span>{product.outside_diameter}</div>}
        {product.overall_width && <div style={{ fontSize:11, color:'#94a3b8' }}><span style={{ color:'#475569' }}>W: </span>{product.overall_width}</div>}
      </td>
      <td style={{ padding:'10px 8px' }}>
        <div style={{ fontSize:12, color:'#94a3b8' }}>{product.closure_type}</div>
        {product.series && <div style={{ fontSize:11, color:'#475569' }}>Series {product.series}</div>}
      </td>
      <td style={{ padding:'10px 8px', textAlign:'center' }}>
        {product.approved_image_score > 0 ? (
          <div>
            <div style={{ fontSize:16, fontWeight:800, color:product.approved_image_score>=0.75?'#10b981':'#f59e0b' }}>{(product.approved_image_score*100).toFixed(0)}</div>
            <div style={{ fontSize:10, color:'#475569' }}>/100</div>
          </div>
        ) : <span style={{ fontSize:11, color:'#1e293b' }}>—</span>}
      </td>
      <td style={{ padding:'10px 16px' }}>
        <Badge text={sc.label} color={sc.color} bg={sc.bg} />
      </td>
    </tr>
  )
}

export default function App() {
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [typeFilter, setTypeFilter] = useState('')
  const [page, setPage] = useState(1)
  const [selectedProduct, setSelectedProduct] = useState(null)
  const queryClient = useQueryClient()

  const filters = { search:search||undefined, image_status:statusFilter||undefined, product_type:typeFilter||undefined, page, per_page:20 }
  const { data:productsData, isLoading } = useProducts(filters)
  const { data:productTypes } = useProductTypes()

  const batchMut = useMutation({
    mutationFn: () => api.post('/match/batch'),
    onSuccess: () => { queryClient.invalidateQueries(['products']); queryClient.invalidateQueries(['stats']) }
  })

  const products = productsData?.products || []
  const totalPages = productsData?.pages || 1

  return (
    <div style={{ minHeight:'100vh', background:'#0a0e1a' }}>
      <div style={{ background:'#050a12', borderBottom:'1px solid #1e293b', padding:'0 32px', height:56, display:'flex', alignItems:'center', justifyContent:'space-between', position:'sticky', top:0, zIndex:50 }}>
        <div style={{ display:'flex', alignItems:'center', gap:12 }}>
          <div style={{ fontSize:20, fontWeight:900, letterSpacing:'-0.02em' }}>
            <span style={{ color:'#3b82f6' }}>PIDME</span>
          </div>
          <div style={{ width:1, height:20, background:'#1e293b' }} />
          <div style={{ fontSize:12, color:'#475569', letterSpacing:'0.05em' }}>Ball Bearings Catalog · motion.com</div>
        </div>
        <button onClick={()=>batchMut.mutate()} disabled={batchMut.isPending}
          style={{ background:batchMut.isPending?'#1e293b':'#1d4ed8', color:'#fff', border:'none', padding:'7px 16px', borderRadius:6, fontSize:12, fontWeight:600 }}>
          {batchMut.isPending ? '⏳ Matching all...' : '🔍 Match All Images'}
        </button>
      </div>

      <div style={{ padding:'24px 32px', maxWidth:1400, margin:'0 auto' }}>
        <StatsBar />
        <StatusBreakdown />

        <div style={{ display:'flex', gap:10, marginBottom:16, alignItems:'center', flexWrap:'wrap' }}>
          <input value={search} onChange={e=>{setSearch(e.target.value);setPage(1)}}
            placeholder="Search SKU, manufacturer, part number..."
            style={{ background:'#111827', border:'1px solid #1e293b', color:'#e2e8f0', padding:'8px 14px', borderRadius:6, fontSize:13, width:300, outline:'none' }} />
          <select value={statusFilter} onChange={e=>{setStatusFilter(e.target.value);setPage(1)}}
            style={{ background:'#111827', border:'1px solid #1e293b', color:'#e2e8f0', padding:'8px 12px', borderRadius:6, fontSize:13 }}>
            <option value="">All Statuses</option>
            {Object.entries(STATUS_CFG).map(([k,v]) => <option key={k} value={k}>{v.label}</option>)}
          </select>
          <select value={typeFilter} onChange={e=>{setTypeFilter(e.target.value);setPage(1)}}
            style={{ background:'#111827', border:'1px solid #1e293b', color:'#e2e8f0', padding:'8px 12px', borderRadius:6, fontSize:13, maxWidth:260 }}>
            <option value="">All Types</option>
            {(productTypes||[]).map(t => <option key={t} value={t}>{t}</option>)}
          </select>
          {(search||statusFilter||typeFilter) && (
            <button onClick={()=>{setSearch('');setStatusFilter('');setTypeFilter('');setPage(1)}}
              style={{ background:'transparent', border:'1px solid #1e293b', color:'#94a3b8', padding:'7px 12px', borderRadius:6, fontSize:12 }}>✕ Clear</button>
          )}
          <div style={{ marginLeft:'auto', fontSize:12, color:'#475569' }}>{productsData?.total||0} products</div>
        </div>

        <div style={{ background:'#0a0e1a', border:'1px solid #1e293b', borderRadius:10, overflow:'hidden' }}>
          <table style={{ width:'100%', borderCollapse:'collapse' }}>
            <thead>
              <tr style={{ background:'#111827', borderBottom:'2px solid #1e293b' }}>
                {['Image','SKU','Manufacturer / Part#','Description','Specifications','Closure','Score','Status'].map(h => (
                  <th key={h} style={{ padding:'10px 8px', textAlign:'left', fontSize:10, fontWeight:700, letterSpacing:'0.08em', color:'#475569', textTransform:'uppercase', paddingLeft:h==='Image'||h==='Status'?16:8 }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {isLoading ? <tr><td colSpan={8}><Spinner /></td></tr>
               : products.length===0 ? <tr><td colSpan={8} style={{ padding:40, textAlign:'center', color:'#475569' }}>No products found</td></tr>
               : products.map(p => <ProductRow key={p.id} product={p} isSelected={selectedProduct===p.id} onSelect={setSelectedProduct} />)}
            </tbody>
          </table>
        </div>

        {totalPages > 1 && (
          <div style={{ display:'flex', justifyContent:'center', gap:8, marginTop:16 }}>
            <button disabled={page<=1} onClick={()=>setPage(p=>p-1)} style={{ background:'#111827', border:'1px solid #1e293b', color:'#94a3b8', padding:'6px 14px', borderRadius:6, fontSize:12, opacity:page<=1?0.4:1 }}>← Prev</button>
            {Array.from({length:totalPages},(_,i)=>i+1).map(p => (
              <button key={p} onClick={()=>setPage(p)} style={{ background:p===page?'#1d4ed8':'#111827', border:'1px solid #1e293b', color:p===page?'#fff':'#94a3b8', padding:'6px 12px', borderRadius:6, fontSize:12, minWidth:36 }}>{p}</button>
            ))}
            <button disabled={page>=totalPages} onClick={()=>setPage(p=>p+1)} style={{ background:'#111827', border:'1px solid #1e293b', color:'#94a3b8', padding:'6px 14px', borderRadius:6, fontSize:12, opacity:page>=totalPages?0.4:1 }}>Next →</button>
          </div>
        )}
        <div style={{ marginTop:24, fontSize:11, color:'#1e293b', textAlign:'center' }}>Click any row to view image candidates · Data sourced from motion.com</div>
      </div>

      {selectedProduct && <CandidatesPanel productId={selectedProduct} onClose={()=>setSelectedProduct(null)} />}
    </div>
  )
}
