export default function NotFound(){
  return (
    <main style={{minHeight:'100vh',display:'grid',placeItems:'center',padding:24,textAlign:'center'}}>
      <div>
        <div style={{fontSize:48,fontWeight:800}}>404</div>
        <h1 style={{margin:'8px 0'}}>هذه الصفحة غير موجودة</h1>
        <p style={{opacity:.72,margin:'0 0 18px'}}>The requested AQLEVON page could not be found.</p>
        <a href="/chat" style={{textDecoration:'none'}}>العودة إلى المحادثات</a>
      </div>
    </main>
  );
}
