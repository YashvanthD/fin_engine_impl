function toggleSection(id) {
            var body = document.getElementById(id);
            if (!body) return;
            var hidden = body.style.display === 'none';
            body.style.display = hidden ? 'block' : 'none';
            var icon = body.parentElement.querySelector('.section-toggle');
            if (icon) icon.textContent = hidden ? '▾' : '▸';
        }
        function toggleCard(id) {
            var body = document.getElementById(id);
            if (!body) return;
            var hidden = body.style.display === 'none';
            body.style.display = hidden ? 'block' : 'none';
            var icon = body.parentElement.querySelector('.card-toggle');
            if (icon) icon.textContent = hidden ? '▾ details' : '▸ details';
        }
        document.addEventListener('DOMContentLoaded', function () {
            // Collapse all card bodies by default for a smoother overview
            var bodies = document.querySelectorAll('.card-body');
            bodies.forEach(function (b) { b.style.display = 'none'; });
            var cardToggles = document.querySelectorAll('.card-toggle');
            cardToggles.forEach(function (t) { t.textContent = '▸ details'; });
        });

// loader will be appended programmatically


// dynamic loader for API doc sections
(async function(){
  const container=document.getElementById('sections-container');
  if(!container) return;
  const manifestUrl = container.dataset && container.dataset.manifestUrl ? container.dataset.manifestUrl : '/static/api_doc_parts/manifest.json';
  const resp=await fetch(manifestUrl);
  const list=await resp.json();
  for(const s of list){
    try{
      const r=await fetch('/static/api_doc_parts/'+s.file);
      const html=await r.text();
      const div=document.createElement('div');
      div.innerHTML=html;
      // append section node(s)
      while(div.firstChild) container.appendChild(div.firstChild);
    }catch(e){console.error('failed to load',s.file,e)}
  }
  // Re-run collapse logic after loading
  if(typeof document !== 'undefined'){
    const bodies=document.querySelectorAll('.card-body');
    bodies.forEach(b=>b.style.display='none');
    const toggles=document.querySelectorAll('.card-toggle');
    toggles.forEach(t=>t.textContent='▸ details');
  }
})();
