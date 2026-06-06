#!/usr/bin/env python3
"""Inject dashboard into web_app.py"""
path = 'prompt-os-engine/ui/web_app.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# Insert dashboard route + helper before @app.get("/export")
old = '@app.get("/export")'

dashboard_code = r'''@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard():
    """Analytics dashboard with 10 toggleable panels."""
    import json as _json

    try: state = io_utils.read_yaml(config.SESSION_STATE_PATH)
    except: state = {}
    try: graph = io_utils.read_json(config.STORY_GRAPH_PATH)
    except: graph = {}
    try: memory = load_memory()
    except: memory = {}
    try: world_pack = io_utils.read_yaml(config.WORLD_PACK_PATH)
    except: world_pack = {}

    api_logs = []
    if config.API_USAGE_PATH.exists():
        for line in config.API_USAGE_PATH.read_text(encoding='utf-8').strip().split('\n'):
            if line.strip():
                try: api_logs.append(_json.loads(line))
                except: pass

    history = state.get('history', [])
    turn = state.get('turn', 0)
    chars = state.get('characters', {})
    total_chars = sum(len(h.get('story','')) for h in history)
    nodes = graph.get('nodes', {})
    edges = graph.get('edges', [])
    prompt_t = sum(e.get('prompt_tokens',0) for e in api_logs)
    comp_t = sum(e.get('completion_tokens',0) for e in api_logs)
    cost = prompt_t/1e6*0.14 + comp_t/1e6*0.28

    js_data = {
        'turn': turn, 'status': state.get('status','SETUP'),
        'char_count': len(chars), 'total_chars': total_chars,
        'node_count': len(nodes), 'cost': round(cost, 4),
        'total_tokens': prompt_t + comp_t,
        'history': history, 'nodes': nodes, 'edges': edges,
        'memory': memory, 'api_logs': api_logs,
        'world_title': world_pack.get('world',{}).get('title',''),
    }
    return HTMLResponse(_build_dashboard(js_data))


def _build_dashboard(d: dict) -> str:
    import json as _json
    data_json = _json.dumps(d, ensure_ascii=False)
    return _DASHBOARD_HTML.replace('{{DATA_JSON}}', data_json).replace('{{WORLD_TITLE}}', d.get('world_title',''))


_DASHBOARD_HTML = r'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>剧情仪表盘</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>
<script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:"Segoe UI","Noto Sans SC",sans-serif;background:#0d1117;color:#c9d1d9;height:100vh;overflow:hidden;display:flex;flex-direction:column;align-items:center}
.db-container{max-width:1500px;width:100%;height:100%;display:flex;flex-direction:column;padding:12px 20px}
.db-header{text-align:center;flex-shrink:0;padding:10px 0;border-bottom:1px solid #30363d;margin-bottom:10px}
.db-header h1{font-size:1.3em;color:#58a6ff}
.db-header a{color:#8b949e;text-decoration:none;font-size:0.8em}
.db-header a:hover{color:#58a6ff}
.db-summary{display:flex;gap:10px;flex-wrap:wrap;flex-shrink:0;margin-bottom:10px}
.db-summary .stat{background:#161b22;border:1px solid #30363d;border-radius:6px;padding:6px 14px;font-size:0.78em;text-align:center;min-width:80px}
.db-summary .stat .val{font-size:1.3em;font-weight:bold;color:#58a6ff}
.db-summary .stat .lbl{color:#8b949e;font-size:0.7em}
.db-toggles{display:flex;gap:6px;flex-wrap:wrap;flex-shrink:0;margin-bottom:10px}
.db-toggle{padding:4px 10px;background:#1c2333;border:1px solid #30363d;border-radius:14px;color:#8b949e;font-size:0.72em;cursor:pointer;transition:0.15s}
.db-toggle:hover{border-color:#58a6ff;color:#58a6ff}
.db-toggle.on{background:#1a3a5c;border-color:#58a6ff;color:#58a6ff}
.db-body{flex:1;overflow-y:auto;min-height:0;display:grid;grid-template-columns:repeat(auto-fill,minmax(420px,1fr));gap:10px;align-content:start}
.db-panel{background:#161b22;border:1px solid #30363d;border-radius:8px;padding:14px 16px;min-height:200px}
.db-panel.hidden{display:none}
.db-panel h3{font-size:0.85em;color:#8b949e;margin-bottom:8px}
.char-card-sm{display:inline-block;background:#0d1117;border:1px solid #30363d;border-radius:6px;padding:8px 12px;margin:4px;font-size:0.78em;vertical-align:top}
.char-card-sm .cn{font-weight:bold;color:#d2a8ff}
.char-card-sm .cr{color:#8b949e;font-size:0.85em}
.char-card-sm .cv{color:#ffa657}
.node-table{width:100%;font-size:0.75em;border-collapse:collapse}
.node-table td,.node-table th{border:1px solid #30363d;padding:3px 6px;text-align:left}
.node-table th{background:#1c2333;color:#8b949e}
canvas{max-height:280px}
</style>
</head>
<body>
<div class="db-container">
<div class="db-header"><h1>🌳 {{WORLD_TITLE}} — 剧情仪表盘</h1><a href="/" class="back-btn">← 返回游戏</a></div>
<div class="db-summary" id="summary"></div>
<div class="db-toggles" id="toggles"></div>
<div class="db-body" id="panels"></div>
</div>
<script>
const D = {{DATA_JSON}};
mermaid.initialize({startOnLoad:false,theme:'dark'});

const panels=[
  {id:'chars',icon:'\ud83c\udfad',title:'角色卡片',render:renderChars},
  {id:'graph',icon:'\ud83c\udf33',title:'剧情图谱',render:renderMermaid},
  {id:'trust',icon:'\ud83d\udcc8',title:'信任曲线',render:renderTrust},
  {id:'timeline',icon:'\u23f1\ufe0f',title:'状态时间线',render:renderTimeline},
  {id:'words',icon:'\ud83d\udcca',title:'字数趋势',render:renderWords},
  {id:'choice',icon:'\ud83c\udfaf',title:'选择偏好',render:renderChoice},
  {id:'api',icon:'\ud83d\udcb0',title:'API用量',render:renderApi},
  {id:'appear',icon:'\ud83d\udc65',title:'角色出场',render:renderAppear},
  {id:'nodetbl',icon:'\ud83d\udccb',title:'节点详情',render:renderNodeTable},
  {id:'branch',icon:'\ud83d\udd00',title:'分支统计',render:renderBranch},
];

const h=D.history||[], nodes=D.nodes||{}, edges=D.edges||[], mem=D.memory||{};

// Summary bar
document.getElementById('summary').innerHTML=[
  {v:D.turn,l:'轮次'},{v:D.status,l:'状态'},{v:D.char_count,l:'角色'},
  {v:D.total_chars.toLocaleString(),l:'总字数'},{v:D.node_count,l:'节点'},
  {v:'$'+D.cost.toFixed(4),l:'API费用'}
].map(function(s){return '<div class="stat"><div class="val">'+s.v+'</div><div class="lbl">'+s.l+'</div></div>';}).join('');

// Toggle buttons
var visible={};panels.forEach(function(p){visible[p.id]=true;});
document.getElementById('toggles').innerHTML=panels.map(function(p){
  return '<button class="db-toggle on" id="btn_'+p.id+'" onclick="togglePanel(\''+p.id+'\')">'+p.icon+' '+p.title+'</button>';
}).join('');

// Render all panels
var body=document.getElementById('panels');
panels.forEach(function(p){
  var div=document.createElement('div');div.className='db-panel';div.id='pnl_'+p.id;
  div.innerHTML='<h3>'+p.icon+' '+p.title+'</h3><div id="ct_'+p.id+'"></div>';
  body.appendChild(div);
});
panels.forEach(function(p){p.render();});

function togglePanel(id){
  visible[id]=!visible[id];
  document.getElementById('btn_'+id).classList.toggle('on',visible[id]);
  document.getElementById('pnl_'+id).classList.toggle('hidden',!visible[id]);
}

function renderChars(){
  var chars=mem.characters||{}, stateChars=(D.history[D.history.length-1]||{}).characters||{};
  var html='';
  for(var k in chars){
    var c=chars[k], scFound=null;
    for(var sk in stateChars){if(stateChars[sk].name===k){scFound=stateChars[sk];break;}}
    var sc=scFound||{};
    html+='<div class="char-card-sm"><div class="cn">'+k+'</div><div class="cr">'+(sc.role||'')+'</div><div class="cv">\u2b50 '+(sc.level||'L0')+' \u00b7 \ud83e\udd1d '+(c.trust*100).toFixed(0)+'%</div></div>';
  }
  document.getElementById('ct_chars').innerHTML=html||'暂无角色';
}

async function renderMermaid(){
  var lines=['graph TD'];
  for(var id in nodes){var n=nodes[id];lines.push('  n'+id+'["T'+n.turn+': '+(n.text||'').slice(0,30)+'"]');}
  for(var i=0;i<edges.length;i++){var e=edges[i];lines.push('  n'+e.from+' -- '+e.choice+' --> n'+e.to);}
  try{
    var result=await mermaid.render('mermaidSvg',lines.join('\n'));
    document.getElementById('ct_graph').innerHTML=result.svg;
  }catch(ex){document.getElementById('ct_graph').innerHTML='<p style="color:#f85149">图谱渲染失败</p>';}
}

function renderTrust(){
  var chars=mem.characters||{}, datasets=[], colors=['#58a6ff','#7ee787','#ffa657','#d2a8ff','#f85149'], ci=0;
  for(var name in chars){
    var th=(chars[name].trust_history||[]).filter(function(x){return x.length>=2;});
    if(th.length<2) continue;
    datasets.push({label:name,data:th.map(function(x){return {x:x[0],y:Math.round(x[1]*100)};}),borderColor:colors[ci%colors.length],tension:0.3,pointRadius:3});
    ci++;
  }
  if(!datasets.length){document.getElementById('ct_trust').innerHTML='<p style="color:#8b949e">数据不足</p>';return;}
  var canvas=document.createElement('canvas');document.getElementById('ct_trust').appendChild(canvas);
  new Chart(canvas,{type:'line',data:{datasets:datasets},options:{scales:{x:{title:{text:'轮次',display:true}},y:{min:0,max:100,title:{text:'信任度%',display:true}}},plugins:{legend:{position:'bottom'}}}});
}

function renderTimeline(){
  var labels={SETUP:'序章',BUILD:'展开',TENSION:'张力',CLIMAX:'高潮',COOLDOWN:'余韵'};
  var colors={SETUP:'#58a6ff',BUILD:'#7ee787',TENSION:'#ffa657',CLIMAX:'#f85149',COOLDOWN:'#d2a8ff'};
  var turns=h.map(function(x){return {turn:x.turn,status:x.status,scene:x.scene};});
  if(!turns.length){document.getElementById('ct_timeline').innerHTML='<p style="color:#8b949e">无数据</p>';return;}
  var canvas=document.createElement('canvas');document.getElementById('ct_timeline').appendChild(canvas);
  var statuses=['SETUP','BUILD','TENSION','CLIMAX','COOLDOWN'], datasets=[];
  for(var i=0;i<statuses.length;i++){
    var s=statuses[i], data=turns.map(function(t){return {x:t.turn,y:1};});
    datasets.push({label:labels[s],data:data.filter(function(_,j){return turns[j].status===s;}),backgroundColor:colors[s],barPercentage:1,categoryPercentage:1});
  }
  new Chart(canvas,{type:'bar',data:{datasets:datasets},options:{indexAxis:'y',scales:{x:{stacked:true,title:{text:'轮次',display:true}},y:{stacked:true,display:false}},plugins:{legend:{position:'bottom'}},aspectRatio:6}});
}

function renderWords(){
  var data=h.map(function(x){return {turn:x.turn,chars:(x.story||'').length};});
  if(!data.length){document.getElementById('ct_words').innerHTML='<p style="color:#8b949e">无数据</p>';return;}
  var canvas=document.createElement('canvas');document.getElementById('ct_words').appendChild(canvas);
  new Chart(canvas,{type:'bar',data:{labels:data.map(function(d){return 'T'+d.turn;}),datasets:[{label:'字数',data:data.map(function(d){return d.chars;}),backgroundColor:'#58a6ff'}]},options:{scales:{y:{title:{text:'字数',display:true}}},plugins:{legend:{display:false}}}});
}

function renderChoice(){
  var counts={A:0,B:0,C:0,D:0,other:0};
  for(var i=0;i<edges.length;i++){var c=edges[i].choice||'?';if('ABCD'.indexOf(c)>=0)counts[c]++;else counts.other++;}
  var labels=[],data=[],bg=[],pal=['#58a6ff','#7ee787','#ffa657','#d2a8ff','#f85149'];
  for(var k in counts){if(counts[k]>0){labels.push(k);data.push(counts[k]);bg.push(pal['ABCD'.indexOf(k)>=0?'ABCD'.indexOf(k):4]);}}
  if(!data.length){document.getElementById('ct_choice').innerHTML='<p style="color:#8b949e">无数据</p>';return;}
  var canvas=document.createElement('canvas');document.getElementById('ct_choice').appendChild(canvas);
  new Chart(canvas,{type:'doughnut',data:{labels:labels,datasets:[{data:data,backgroundColor:bg}]},options:{plugins:{legend:{position:'bottom'}}}});
}

function renderApi(){
  var logs=D.api_logs||[];
  if(!logs.length){document.getElementById('ct_api').innerHTML='<p style="color:#8b949e">暂无API调用</p>';return;}
  var canvas=document.createElement('canvas');document.getElementById('ct_api').appendChild(canvas);
  var labels=logs.map(function(_,i){return '#'+(i+1);});
  new Chart(canvas,{type:'bar',data:{labels:labels,datasets:[
    {label:'Prompt',data:logs.map(function(l){return l.prompt_tokens||0;}),backgroundColor:'#58a6ff'},
    {label:'Completion',data:logs.map(function(l){return l.completion_tokens||0;}),backgroundColor:'#7ee787'}
  ]},options:{scales:{x:{stacked:true},y:{stacked:true,title:{text:'Tokens',display:true}}},plugins:{legend:{position:'bottom'}}}});
}

function renderAppear(){
  var charNames=Object.keys(mem.characters||{}), counts={};
  charNames.forEach(function(n){counts[n]=0;});
  for(var i=0;i<h.length;i++){var s=h[i].story||'';for(var j=0;j<charNames.length;j++){if(s.indexOf(charNames[j])>=0) counts[charNames[j]]++;}}
  var hasData=Object.values(counts).some(function(x){return x>0;});
  if(!hasData){document.getElementById('ct_appear').innerHTML='<p style="color:#8b949e">无出场数据</p>';return;}
  var canvas=document.createElement('canvas');document.getElementById('ct_appear').appendChild(canvas);
  new Chart(canvas,{type:'bar',data:{labels:charNames,datasets:[{label:'出场次数',data:charNames.map(function(n){return counts[n];}),backgroundColor:'#d2a8ff'}]},options:{plugins:{legend:{display:false}},scales:{y:{title:{text:'轮次',display:true}}}}});
}

function renderNodeTable(){
  var html='<table class="node-table"><tr><th>ID</th><th>轮次</th><th>场景</th><th>状态</th><th>内容</th><th>分支</th></tr>';
  for(var id in nodes){
    var n=nodes[id], choices=[];
    for(var k in (n.choices||{})){if(n.choices[k]) choices.push(k+'\u2192'+n.choices[k]);}
    html+='<tr><td>'+id+'</td><td>'+n.turn+'</td><td>'+n.scene+'</td><td>'+n.status+'</td><td>'+(n.text||'').slice(0,50)+'</td><td>'+choices.join(', ')+'</td></tr>';
  }
  html+='</table>';
  document.getElementById('ct_nodetbl').innerHTML=html;
}

function renderBranch(){
  var leafCount=0, maxDepth=0;
  for(var id in nodes){
    var n=nodes[id], hasChild=false;
    for(var k in (n.choices||{})){if(n.choices[k]) hasChild=true;}
    if(!hasChild) leafCount++;
    var d=0, p=n;
    while(p&&p.parent){d++;p=nodes[p.parent];}
    if(d>maxDepth) maxDepth=d;
  }
  document.getElementById('ct_branch').innerHTML='<div style="display:flex;gap:16px;flex-wrap:wrap;">'+
    '<div class="stat"><div class="val">'+D.node_count+'</div><div class="lbl">总节点</div></div>'+
    '<div class="stat"><div class="val">'+edges.length+'</div><div class="lbl">总分支</div></div>'+
    '<div class="stat"><div class="val">'+leafCount+'</div><div class="lbl">叶子节点</div></div>'+
    '<div class="stat"><div class="val">'+maxDepth+'</div><div class="lbl">最大深度</div></div>'+
    '<div class="stat"><div class="val">'+D.turn+'</div><div class="lbl">总轮次</div></div>'+
  '</div>';
}
</script>
</body>
</html>'''


@app.get("/export")'''

content = content.replace(old, dashboard_code)

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
print('Dashboard injected successfully')
