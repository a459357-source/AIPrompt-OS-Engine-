"""
离线数据完整性检查：不使用AI API，检查现有游戏数据的一致性
"""
import json, yaml, sys
from pathlib import Path

ROOT = Path("prompt-os-engine")
errors = 0

def check(what, ok, detail=""):
    global errors
    if ok:
        print(f"  ✅ {what}")
    else:
        print(f"  ❌ {what}  {detail}")
        errors += 1

# ── 1. 加载所有数据文件 ──
print("\n📂 1. 加载数据文件...")
session = yaml.safe_load((ROOT / "session_state.yaml").read_text(encoding="utf-8"))
memory = json.loads((ROOT / "data/memory.json").read_text(encoding="utf-8"))
graph = json.loads((ROOT / "data/story_graph.json").read_text(encoding="utf-8"))
with open(ROOT / "world_pack.yaml", encoding="utf-8") as f:
    world = yaml.safe_load(f)
wp = world.get("world", {})

check("session_state.yaml", session is not None)
check("memory.json", memory is not None)
check("story_graph.json", graph is not None)
check("world_pack.yaml", wp is not None)

# ── 2. session_state 完整性 ──
print("\n📋 2. session_state 检查...")
state_turn = session.get("turn", 0)
state_status = session.get("status", "SETUP")
state_scene = session.get("scene", "")
chars = session.get("characters", {})
history = session.get("history", [])

check("turn > 0", state_turn > 0, f"turn={state_turn}")
check("status 合法", state_status in ("SETUP","BUILD","TENSION","CLIMAX","COOLDOWN"), f"status={state_status}")
check("scene 非空", len(state_scene) > 0)
check("characters >= 2", len(chars) >= 2, f"共{len(chars)}个")
check("history > 0", len(history) > 0, f"共{len(history)}条")

# 检查每个character字段完整性
for key, c in chars.items():
    name = c.get("name", "?")
    has_name = len(name) > 0
    has_role = len(c.get("role", "")) > 0
    has_level = c.get("level", "L0") in ("L0","L1","L2","L3","L4")
    check(f"  {name}: 有姓名+身份+等级", has_name and has_role and has_level)

# 检查history一致性
last_turn = history[-1].get("turn", 0) if history else 0
check("history最后turn与state.turn一致", last_turn == state_turn, f"history={last_turn} vs state={state_turn}")

for h in history:
    has_story = len(h.get("story", "")) > 10 if h.get("turn", 0) > 0 else True
    if not has_story:
        check(f"  history T{h.get('turn','?')} story过短", False, f"{len(h.get('story',''))}字")

# ── 3. memory.json 完整性 ──
print("\n🧠 3. memory.json 检查...")
mem_chars = memory.get("characters", {})
check("memory characters >= session characters", len(mem_chars) >= len(chars),
      f"memory={len(mem_chars)} vs session={len(chars)}")

for name, data in mem_chars.items():
    trust = data.get("trust", None)
    tier = data.get("tier", "")
    flags = data.get("flags", [])
    mh = data.get("metric_history", {})
    check(f"  {name}: trust={trust}", trust is not None and 0 <= trust <= 1)
    check(f"  {name}: tier非空", len(tier) > 0)
    if trust is not None and trust > 0:
        check(f"  {name}: metric_history有数据", len(mh) > 0)

# 势力检查
factions = memory.get("factions", {})
check("factions 存在", isinstance(factions, dict), f"共{len(factions)}个")
# 注意：当前factions可能是空的，这是已知问题
for fname, fdata in factions.items():
    rep = fdata.get("reputation", None)
    check(f"  [{fname}] reputation有效", rep is not None and 0 <= rep <= 1)

# 物品检查
artifacts = memory.get("artifacts", {})
check("artifacts 存在", isinstance(artifacts, dict), f"共{len(artifacts)}个")
for aname, adata in artifacts.items():
    status = adata.get("status", "?")
    check(f"  [{aname}] status={status}", status in ("active","lost","destroyed","sealed"))

# ── 4. story_graph 完整性 ──
print("\n🌳 4. story_graph 检查...")
nodes = graph.get("nodes", {})
edges = graph.get("edges", [])
current = graph.get("current_node", "?")
check("有节点", len(nodes) > 0)
check("current_node存在", current in nodes, f"current={current}")
check("节点数>=边数-1", len(nodes) >= len(edges), f"nodes={len(nodes)} edges={len(edges)}")

for nid, node in nodes.items():
    turn = node.get("turn", 0)
    text = node.get("text", "")
    scene = node.get("scene", "")
    check(f"  Node {nid}: turn={turn} scene非空", len(scene) > 0 or turn == 0)

# ── 5. world_pack 完整性 ──
print("\n🌍 5. world_pack 检查...")
wp_factions = wp.get("factions", [])
wp_chars = wp.get("characters", [])
wp_arts = wp.get("artifacts", [])
wp_rels = wp.get("relationship_system", {})
check("势力 >= 3", len(wp_factions) >= 3, f"共{len(wp_factions)}个")
check("角色 >= 3", len(wp_chars) >= 3, f"共{len(wp_chars)}个")
check("物品 >= 1", len(wp_arts) >= 1, f"共{len(wp_arts)}个")
check("关系系统存在", len(wp_rels) > 0)

# 势力新字段检查
for f in wp_factions:
    name = f.get("name", "?")
    has_territory = len(f.get("controlledTerritories", [])) > 0
    has_orgs = len(f.get("subordinateOrganizations", [])) > 0
    has_assets = len(f.get("keyAssets", [])) > 0
    has_power = isinstance(f.get("power"), dict)
    check(f"  [{name}] 掌控范围字段完整", has_territory and has_orgs and has_assets and has_power)

# ── 6. 交叉引用检查 ──
print("\n🔗 6. 交叉引用检查...")
# 6a. session characters vs memory characters vs world_pack characters
session_names = set(c.get("name", "") for c in chars.values())
mem_names = set(mem_chars.keys())
wp_names = set(c.get("name", "") for c in wp_chars)
common = session_names & mem_names
check("session角色在memory中", len(common) >= 2, f"共同: {len(common)}/{len(session_names)}")

# 6b. 势力在world_pack和memory中对应
if factions:
    wp_fac_names = set(f.get("name","") for f in wp_factions)
    mem_fac_names = set(factions.keys())
    common_fac = wp_fac_names & mem_fac_names
    check("势力world_pack↔memory一致", len(common_fac) >= len(wp_fac_names) * 0.5, 
          f"共同={len(common_fac)}, wp={len(wp_fac_names)}, mem={len(mem_fac_names)}")

# 6c. 角色→势力绑定
for wc in wp_chars:
    name = wc.get("name", "")
    faction = wc.get("faction", "")
    if faction and name in mem_chars:
        mem_fac = mem_chars[name].get("faction", "")
        if not mem_fac:
            check(f"  {name} faction='{faction}' 但memory中无faction字段", False)
        else:
            check(f"  {name} faction='{faction}' ↔ memory='{mem_fac}'", faction == mem_fac or mem_fac == "")

# ── 7. 仪表盘HTML生成 ──
print("\n📊 7. 仪表盘检查...")
sys.path.insert(0, str(ROOT))
try:
    from engine.dashboard import build_html, collect_data
    data = collect_data()
    html = build_html(data)
    check("仪表盘数据收集成功", data.get("turn", 0) > 0)
    check("仪表盘HTML生成成功", len(html) > 5000, f"{len(html)}字节")
    
    # 检查关键面板是否在HTML中
    panels = ["sec-chars", "sec-graph", "sec-trust", "sec-factions", "sec-artifacts", "sec-factionPower"]
    for p in panels:
        check(f"  面板 {p}", p in html)
except Exception as e:
    check("仪表盘生成异常", False, str(e))

# ── 8. Analytics 计算 ──
print("\n📈 8. Analytics 检查...")
try:
    from engine.analytics import compute_all
    a = compute_all()
    check("compute_all 成功", isinstance(a, dict))
    for key in ["metrics_curves", "status_timeline", "choice_stats", "faction_power", "artifacts"]:
        check(f"  {key} 存在", key in a)
except Exception as e:
    check("Analytics异常", False, str(e))

# ── 总结 ──
print(f"\n{'='*40}")
if errors == 0:
    print("✅ 全部离线检查通过！")
else:
    print(f"⚠️ 共 {errors} 个问题")
print(f"{'='*40}")
