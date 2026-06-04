/* charts.js -- Chart.js helpers (radar comparisons + dataset overview) */
const Charts = (() => {
  const GREEN = '#4f9d6e', GREEN_D = '#2f5d43', GOLD = '#e6a23c', CLAY = '#e15241';
  const GRADE = { a:'#1a8c4a', b:'#73b531', c:'#f3c423', d:'#ee8c2a', e:'#e15241' };
  const FONT = "'Outfit', sans-serif";
  Chart.defaults.font.family = FONT;
  Chart.defaults.color = '#6a7a70';
  const registry = {};

  function destroy(id){ if(registry[id]){ registry[id].destroy(); delete registry[id]; } }

  function hexA(hex, a){
    const n = parseInt(hex.slice(1),16);
    return `rgba(${(n>>16)&255},${(n>>8)&255},${n&255},${a})`;
  }

  // ---- Radar comparing several products across shared dimensions --------
  function radar(canvasId, labels, series){
    destroy(canvasId);
    const palette = [GREEN_D, GREEN, GOLD];
    const ds = series.map((s,i) => {
      const c = s.color || palette[i % palette.length];
      return {
        label:s.label, data:s.data,
        borderColor:c, backgroundColor:hexA(c,.16),
        pointBackgroundColor:c, borderWidth:2, pointRadius:3,
      };
    });
    registry[canvasId] = new Chart(document.getElementById(canvasId), {
      type:'radar',
      data:{ labels, datasets:ds },
      options:{
        responsive:true, maintainAspectRatio:true,
        scales:{ r:{
          suggestedMin:0, suggestedMax:100, ticks:{stepSize:25,backdropColor:'transparent',font:{size:9}},
          grid:{color:'#e3f3e9'}, angleLines:{color:'#dde7e0'},
          pointLabels:{font:{size:11,weight:'500'},color:'#2f5d43'}
        }},
        plugins:{ legend:{position:'bottom',labels:{boxWidth:12,padding:14,font:{size:12}}},
          tooltip:{callbacks:{label:c=>`${c.dataset.label}: ${c.formattedValue}/100`}}}
      }
    });
  }

  function bar(canvasId, labels, data, opts={}){
    destroy(canvasId);
    const colors = opts.gradeColors ? labels.map(l => GRADE[l.toLowerCase()] || GREEN) : (opts.colors || GREEN);
    registry[canvasId] = new Chart(document.getElementById(canvasId), {
      type:'bar',
      data:{ labels, datasets:[{ data, backgroundColor:colors, borderRadius:8, maxBarThickness:46 }] },
      options:{
        indexAxis: opts.horizontal ? 'y':'x',
        responsive:true, maintainAspectRatio:true,
        plugins:{ legend:{display:false}, tooltip:{callbacks:{label:c=>` ${c.formattedValue}${opts.unit||''}`}}},
        scales:{
          x:{ grid:{display:!opts.horizontal,color:'#eef4f0'}, ticks:{font:{size:11}} },
          y:{ grid:{display:opts.horizontal?false:true,color:'#eef4f0'}, beginAtZero:true, ticks:{font:{size:11}} }
        }
      }
    });
  }

  function doughnut(canvasId, labels, data){
    destroy(canvasId);
    const shades = ['#2f5d43','#3a7355','#4f9d6e','#6cbb8a','#8fcfa6','#bfe3cc','#d8efe0','#a7d9bb','#5fae82','#7cc498'];
    registry[canvasId] = new Chart(document.getElementById(canvasId), {
      type:'doughnut',
      data:{ labels, datasets:[{ data, backgroundColor:labels.map((_,i)=>shades[i%shades.length]), borderWidth:2, borderColor:'#fff' }] },
      options:{ responsive:true, maintainAspectRatio:true, cutout:'58%',
        plugins:{ legend:{position:'right',labels:{boxWidth:11,padding:8,font:{size:11}}} } }
    });
  }

  return { radar, bar, doughnut, destroy, GRADE };
})();
