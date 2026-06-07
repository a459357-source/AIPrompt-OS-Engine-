"""
端到端完整测试 + HTML报告生成
"""
import requests, json, yaml, time, sys
from pathlib import Path
from datetime import datetime

BASE = "http://127.0.0.1:8765"
ROOT = Path("prompt-os-engine")
LOG = []

def post(url, data=None, timeout=180, allow_redirects=True):
    if data is None: data = {}
    r = requests.post(f"{BASE}{url}", data=data, timeout=timeout, allow_redirects=allow_redirects)
    if not allow_redirects and r.status_code in (302, 303):
        return r
    r.raise_for_status()
    return r

def get_json(url):
    return requests.get(f"{BASE}{url}", timeout=30).json()

def log(section, content):
    LOG.append({"time": datetime.now().isoformat(), "section": section, "content": content})
    print(f"  [{section}] {str(content)[:80]}")

# ═══════════════════════════════════════════════════════
# STEP 1: 创建新故事
# ═══════════════════════════════════════════════════════
print("\n" + "="*60)
print("📖 STEP 1: 创建新故事")
print("="*60)

story_config = {
    "title": "星海迷途",
    "world": "2157年，人类在火星发现古代文明遗迹「星门」，打开了通往银河系各地的通道。三大势力争夺星门控制权，一艘名为回声号的调查船被卷入其中。",
    "genre": "科幻 / 冒险 / 悬疑",
    "scene": "火星轨道站「回声号」舰桥",
    "main_goal": "找到星门的真正起源，阻止各方势力引爆星际战争",
}

log("故事设定", story_config)

chars_config = [
    {"name": "林夜", "isMain": True, "role_tags": ["调查船船长", "前特种部队"], 
     "personality_tags": ["冷静", "果断", "内敛"], "appearance": "黑发灰瞳，左脸旧伤疤",
     "relationship": ["自身"], "goal": "揭开星门之谜",
     "secret": "曾执行过涉及星门的黑色行动", "background": "前联邦军特种部队"},
    {"name": "艾琳", "isMain": False, "role_tags": ["考古语言学家", "星门研究员"],
     "personality_tags": ["热情", "好奇", "敏感"], "appearance": "银白长发，紫色眼瞳",
     "relationship": ["同事"], "goal": "解码星门文字",
     "secret": "体内植入了星门碎片", "background": "联盟科学院研究员"},
    {"name": "白璃", "isMain": False, "role_tags": ["情报商人", "自由航行者"],
     "personality_tags": ["狡猾", "幽默", "重情义"], "appearance": "红色短发，左耳三个耳环",
     "relationship": ["朋友"], "goal": "赚够钱买飞船",
     "secret": "曾是帝国情报局特工", "background": "星际黑市长大"},
]
log("角色设定", [c["name"] for c in chars_config])

factions_config = [
    {"name": "地球联邦", "type": "government", "description": "掌控星门安保的母星政府",
     "goals": ["垄断星门控制权"], "controlledTerritories": ["火星轨道","联邦首都"],
     "subordinateOrganizations": ["联邦舰队司令部"], "keyAssets": ["星门主控站"],
     "power": {"military":80,"economic":70,"political":85,"technology":60},
     "influence":85, "relation_to_player":"hostile", "leader":"卡尔森上将"},
    {"name": "自由航行者联盟", "type": "guild", "description": "独立船长的互助组织",
     "goals": ["打破星门垄断"], "controlledTerritories": ["自由港"],
     "subordinateOrganizations": ["商船工会"], "keyAssets": ["加密通讯网"],
     "power": {"military":30,"economic":50,"political":40,"technology":55},
     "influence":55, "relation_to_player":"ally", "leader":"白璃"},
    {"name": "古代守护者", "type": "religion", "description": "崇拜星门建造者的神秘组织",
     "goals": ["封印所有星门"], "controlledTerritories": ["地下神殿"],
     "subordinateOrganizations": ["圣殿骑士团"], "keyAssets": ["古代圣物"],
     "power": {"military":45,"economic":20,"political":30,"technology":90},
     "influence":65, "relation_to_player":"enemy", "leader":"大祭司"},
]
log("势力设定", [f["name"] for f in factions_config])

artifacts_config = [
    {"name": "星门主钥", "type": "world", "description": "能完全控制星门网络的古代装置",
     "ownerType":"none","ownerId":"","importance":95,
     "abilities":["控制星门","关闭通道"], "tags":["古代遗物","争夺目标"]},
    {"name": "解码石板", "type": "personal", "description": "刻有古代文字的金属板",
     "ownerType":"character","ownerId":"艾琳","importance":80,
     "abilities":["解读文字","定位遗迹"], "tags":["研究工具","线索"]},
]
log("物品设定", [a["name"] for a in artifacts_config])

r = post("/new", data={
    "title": story_config["title"],
    "world": story_config["world"],
    "genre": story_config["genre"],
    "scene": story_config["scene"],
    "main_goal": story_config["main_goal"],
    "chars_json": json.dumps(chars_config),
    "rel_system": json.dumps({"stages": ["崩坏","敌视","对立","冷漠","疏远","陌生","认识","信赖","盟友","羁绊"], "affection": 30}),
    "factions_json": json.dumps(factions_config),
    "artifacts_json": json.dumps(artifacts_config),
    "custom_rules": json.dumps({"stats": [{"key":"trust","label":"信任度","max":100},{"key":"knowledge","label":"星门知识","max":100}]}),
}, allow_redirects=False)  # POST /new redirects to GET /
log("创建结果", f"HTTP {r.status_code}")

# ═══════════════════════════════════════════════════════
# STEP 2-8: 游戏回合
# ═══════════════════════════════════════════════════════
turns_log = []

# Turn 1: start
print("\n🎮 STEP 2: 开篇...")
r = post("/api/start")
data = r.json()
turns_log.append({"round": 1, "choice": "开篇", "story": data["story"][:200], 
                   "turn": data["state"]["turn"], "status": data["state"]["status"],
                   "scene": data["state"]["scene"]})
log("开篇", f"T{data['state']['turn']} {data['state']['status']} {data['story'][:60]}...")
time.sleep(2)

# Turns 2-6: choices
choices = [
    ("A", "调查星门异常信号"),
    ("B", "与艾琳商议对策"), 
    ("A", "深入调查古代遗迹"),
    ("D", "联系自由航行者联盟"),
    ("B", "潜入联邦控制区"),
]
for i, (choice, desc) in enumerate(choices):
    print(f"\n🔄 STEP {i+3}: 第{i+2}轮 (选择{choice}: {desc})...")
    r = post("/api/next", {"choice": choice})
    data = r.json()
    turns_log.append({"round": i+2, "choice": f"{choice} - {desc}", 
                       "story": data["story"][:200],
                       "turn": data["state"]["turn"], "status": data["state"]["status"],
                       "scene": data["state"]["scene"]})
    log(f"第{i+2}轮", f"T{data['state']['turn']} {data['state']['status']} {data['story'][:60]}...")
    time.sleep(3)

# Turns 7-8: custom
customs = ["调查星门控制站的异常能量波动", "与艾琳讨论星门碎片共鸣的可能含义"]
for custom in customs:
    print(f"\n✏️ 自定义: {custom}...")
    r = post("/api/next", {"choice": custom})
    data = r.json()
    turns_log.append({"round": len(turns_log)+1, "choice": f"自定义: {custom}", 
                       "story": data["story"][:200],
                       "turn": data["state"]["turn"], "status": data["state"]["status"],
                       "scene": data["state"]["scene"]})
    log("自定义", f"T{data['state']['turn']} {data['state']['status']} {data['story'][:60]}...")
    time.sleep(3)

# ═══════════════════════════════════════════════════════
# STEP 9: 收集所有数据
# ═══════════════════════════════════════════════════════
print("\n📊 收集数据...")

game_state = get_json("/api/game-state")
npcs_data = get_json("/api/npcs")
dashboard = get_json("/api/dashboard")
history_data = get_json("/api/history")

# Read local files
with open(ROOT / "session_state.yaml", encoding="utf-8") as f:
    session = yaml.safe_load(f)
memory = json.loads((ROOT / "data/memory.json").read_text(encoding="utf-8"))
graph = json.loads((ROOT / "data/story_graph.json").read_text(encoding="utf-8"))

log("数据收集", f"session={session['turn']}轮 memory={len(memory['characters'])}角色")

# ═══════════════════════════════════════════════════════
# STEP 10: 生成HTML报告
# ═══════════════════════════════════════════════════════
print("\n📄 生成HTML报告...")

# Build story config table
story_rows = "".join(f"<tr><td>{k}</td><td>{v}</td></tr>" for k,v in story_config.items())

# Build character cards
char_cards = ""
for c in chars_config:
    mem = memory["characters"].get(c["name"], {})
    trust = int(mem.get("trust",0.5)*100)
    tier = mem.get("tier","?")
    flags = ", ".join(mem.get("flags",[]))
    trust_html = ""
    if not c['isMain']:
        trust_html = f'<div class="trust-bar"><div class="trust-fill" style="width:{trust}%"></div></div><div class="dim">信任度: {trust}% | 事件: {flags or "无"}</div>'
    char_cards += f"""
    <div class="card">
      <div class="card-title">{'⭐' if c['isMain'] else '👤'} {c['name']} <span class="badge">{tier}</span></div>
      <div class="dim">身份: {', '.join(c['role_tags'])}</div>
      <div class="dim">外貌: {c.get('appearance', '') or '未设定'}</div>
      <div class="dim">性格: {', '.join(c['personality_tags'])}</div>
      <div class="dim">背景: {c.get('background', '') or '未设定'}</div>
      <div class="dim">能力: {c.get('special_ability', '') or '未设定'}</div>
      <div class="dim">目标: {c['goal']}</div>
      <div class="dim">🔒秘密: {c['secret']}</div>
      {trust_html}
    </div>"""

# Build faction cards
faction_cards = ""
for f in factions_config:
    mem_f = memory["factions"].get(f["name"], {})
    rep = int(mem_f.get("reputation",0.5)*100)
    pw = f["power"]
    faction_cards += f"""
    <div class="card">
      <div class="card-title">🏛️ {f['name']} <span class="badge">{f['type']}</span></div>
      <div class="dim">对主角: {f['relation_to_player']} | 声望: {rep}% | 影响力: {f['influence']}</div>
      <div class="dim">控制区域: {', '.join(f['controlledTerritories'])}</div>
      <div class="dim">关键资产: {', '.join(f['keyAssets'])}</div>
      <div class="dim">实力: 军事{pw['military']} 经济{pw['economic']} 政治{pw['political']} 科技{pw['technology']}</div>
    </div>"""

# Build artifact cards
artifact_cards = ""
for a in artifacts_config:
    mem_a = memory["artifacts"].get(a["name"], {})
    owner = mem_a.get("ownerId","?") or "无"
    status = mem_a.get("status","?")
    transfers = len(mem_a.get("transferHistory",[]))
    artifact_cards += f"""
    <div class="card">
      <div class="card-title">🗝️ {a['name']} <span class="badge">{a['type']}</span></div>
      <div class="dim">持有者: {owner} | 状态: {status} | 转移: {transfers}次</div>
      <div class="dim">能力: {', '.join(a['abilities'])}</div>
      <div class="dim">标签: {', '.join(a['tags'])}</div>
    </div>"""

# Build turn log
turn_rows = ""
for t in turns_log:
    turn_rows += f"""
    <tr>
      <td>T{t['turn']}</td>
      <td>{t['choice']}</td>
      <td>{t['status']}</td>
      <td>{t['scene'][:30]}</td>
      <td>{t['story'][:120]}</td>
    </tr>"""

# Dashboard stats
dash_stats = dashboard
analytics = dash_stats.get("analytics", {})
summ = analytics.get("summary", {})
au = analytics.get("api_usage", {}).get("totals", {})
bs = analytics.get("branch_stats", {})

dashboard_html = f"""
<div class="stats-grid">
  <div class="stat"><big>{dash_stats.get('turn','?')}</big><small>总轮次</small></div>
  <div class="stat"><big>{dash_stats.get('status','?')}</big><small>当前状态</small></div>
  <div class="stat"><big>{dash_stats.get('character_count','?')}</big><small>角色数</small></div>
  <div class="stat"><big>{dash_stats.get('node_count','?')}</big><small>剧情节点</small></div>
  <div class="stat"><big>{dash_stats.get('branch_count','?')}</big><small>分支数</small></div>
  <div class="stat"><big>{dash_stats.get('word_count','?'):,}</big><small>总字数</small></div>
  <div class="stat"><big>{dash_stats.get('api_calls','?')}</big><small>API调用</small></div>
  <div class="stat"><big>${au.get('cost_usd',0):.4f}</big><small>费用</small></div>
</div>
<div class="dim mt">📊 分支统计: 总节点{bs.get('total_nodes','?')} | 叶子{bs.get('leaf_count','?')} | 深度{bs.get('max_depth','?')} | 平均分支{bs.get('avg_branches','?')}</div>
"""

# Metrics
fp = analytics.get("faction_power", {})
pw_rows = ""
if fp.get("datasets"):
    for ds in fp["datasets"]:
        d = ds["data"]
        pw_rows += f"<tr><td>{ds['name']}</td><td>{d[0]}</td><td>{d[1]}</td><td>{d[2]}</td><td>{d[3]}</td></tr>"

arts_data = analytics.get("artifacts", [])
art_rows = "".join(f"<tr><td>{a['name']}</td><td>{a.get('type','?')}</td><td>{a.get('ownerId','无')}</td><td>{a.get('importance','?')}</td><td>{a.get('status','?')}</td><td>{a.get('transferCount',0)}</td></tr>" for a in arts_data)

mc = analytics.get("metrics_curves", {})
trust_curve = mc.get("trust", {})
trust_datasets = trust_curve.get("datasets", [])
trust_rows = ""
for ds in trust_datasets:
    vals = ds.get("data", [])
    trust_rows += f"<tr><td>{ds['name']}</td><td>{vals[-1] if vals else '?'}%</td><td>{len(vals)}个数据点</td></tr>"

# Character trust from API
char_trust_rows = ""
for c in npcs_data.get("characters", []):
    char_trust_rows += f"<tr><td>{c['name']}</td><td>{c.get('trust_pct','?')}%</td><td>{c.get('faction','-')}</td><td>{len(c.get('flags',[]))}个事件</td></tr>"

report = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="utf-8"><title>星海迷途 — 端到端测试报告</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{background:#0d1117;color:#c9d1d9;font-family:system-ui,sans-serif;padding:20px;max-width:1200px;margin:0 auto}}
h1{{color:#58a6ff;font-size:24px;margin-bottom:4px}}
h2{{color:#58a6ff;font-size:18px;margin:24px 0 12px;border-bottom:1px solid #21262d;padding-bottom:6px}}
h3{{color:#8b949e;font-size:14px;margin:12px 0 8px}}
.subtitle{{color:#8b949e;font-size:13px;margin-bottom:20px}}
.card{{background:#161b22;border:1px solid #21262d;border-radius:8px;padding:14px;margin:8px 0}}
.card-title{{font-size:15px;font-weight:700;margin-bottom:6px}}
.badge{{display:inline-block;background:#1f6feb33;color:#58a6ff;border:1px solid #1f6feb44;border-radius:10px;padding:1px 8px;font-size:11px;margin-left:4px}}
.dim{{color:#8b949e;font-size:12px;line-height:1.6}}
.mt{{margin-top:8px}}
.trust-bar{{height:8px;background:#21262d;border-radius:4px;margin:6px 0;overflow:hidden}}
.trust-fill{{height:100%;background:linear-gradient(90deg,#da3633,#d29922,#3fb950);border-radius:4px}}
.stats-grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}}
.stat{{background:#161b22;border:1px solid #21262d;border-radius:8px;padding:12px;text-align:center}}
.stat big{{display:block;font-size:22px;font-weight:700;color:#58a6ff}}
.stat small{{color:#8b949e;font-size:11px}}
table{{width:100%;border-collapse:collapse;font-size:13px;margin:8px 0}}
th{{text-align:left;padding:8px 10px;background:#161b22;color:#8b949e;font-weight:600;border-bottom:1px solid #21262d}}
td{{padding:8px 10px;border-bottom:1px solid #21262d;vertical-align:top}}
tr:hover td{{background:#161b22}}
.green{{color:#3fb950}}
.red{{color:#da3633}}
.yellow{{color:#d29922}}
.footer{{text-align:center;color:#484f58;font-size:11px;margin-top:40px;padding-top:20px;border-top:1px solid #21262d}}
</style></head>
<body>
<h1>🚀 星海迷途 — 端到端测试报告</h1>
<div class="subtitle">生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | 引擎: Prompt OS Galgame Runtime v1 | 模型: deepseek-chat</div>

<h2>📖 1. 故事设定</h2>
<table>{story_rows}</table>

<h2>👥 2. 角色设定（初始3人 + 游戏中新增）</h2>
{char_cards}

<h2>🏛️ 3. 势力设定</h2>
{faction_cards}

<h2>🗝️ 4. 关键物品</h2>
{artifact_cards}

<h2>🎮 5. 游戏流程（{len(turns_log)}轮）</h2>
<table>
<tr><th>轮次</th><th>选择</th><th>状态</th><th>场景</th><th>故事摘要</th></tr>
{turn_rows}
</table>

<h2>📊 6. 仪表盘概览</h2>
{dashboard_html}

<h2>📈 7. 角色信任度变化</h2>
<table>
<tr><th>角色</th><th>当前信任度</th><th>数据点</th></tr>
{trust_rows}
</table>

<h2>👤 8. NPC详情（API）</h2>
<table>
<tr><th>角色</th><th>信任度</th><th>势力</th><th>事件</th></tr>
{char_trust_rows}
</table>

<h2>⚔️ 9. 势力实力</h2>
<table>
<tr><th>势力</th><th>军事</th><th>经济</th><th>政治</th><th>科技</th></tr>
{pw_rows}
</table>

<h2>🗝️ 10. 物品状态</h2>
<table>
<tr><th>物品</th><th>类型</th><th>持有者</th><th>重要度</th><th>状态</th><th>转移</th></tr>
{art_rows}
</table>

<h2>📜 11. 完整历史（API）</h2>
<p class="dim">共 {history_data.get('total',0)} 条历史记录</p>
{"".join(f'<div class="card"><div class="card-title">T{t["turn"]} [{t["status"]}] {t.get("scene","")}</div><div class="dim">选择: {t.get("choice","?")}</div><div class="dim" style="white-space:pre-wrap;margin-top:4px">{t.get("story","")}</div></div>' for t in history_data.get("turns",[])[-5:])}

<div class="footer">Prompt OS Galgame Runtime v1 · 端到端自动化测试 · {datetime.now().strftime('%Y-%m-%d %H:%M')}</div>
</body></html>"""

output_path = ROOT / "output" / "e2e_report.html"
output_path.parent.mkdir(parents=True, exist_ok=True)
output_path.write_text(report, encoding="utf-8")
print(f"\n✅ 报告已生成: {output_path}")
print(f"   大小: {len(report):,} 字节")
