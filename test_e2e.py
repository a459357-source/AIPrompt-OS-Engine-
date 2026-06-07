"""
端到端测试：模拟真实用户操作
1. 创建新故事
2. 开始游戏
3. 5轮选择 + 2轮自定义输入
4. 检查角色/势力/物品/仪表盘数据
"""
import requests
import json
import sys
import time

BASE = "http://127.0.0.1:8765"

def post(url, data=None, follow_redirects=True):
    if data is None:
        data = {}
    r = requests.post(f"{BASE}{url}", data=data, timeout=120, allow_redirects=follow_redirects)
    if not follow_redirects and r.status_code in (302, 303):
        return r
    r.raise_for_status()
    return r

def get(url):
    r = requests.get(f"{BASE}{url}", timeout=30)
    r.raise_for_status()
    return r

def get_json(url):
    r = get(url)
    return r.json()

def check(what, ok):
    if ok:
        print(f"  ✅ {what}")
    else:
        print(f"  ❌ {what}")
        return False
    return True

errors = 0

# ── 1. 创建新故事 ──
print("\n📖 1. 创建新故事...")
r = post("/new", follow_redirects=False, data={
    "title": "星海迷途",
    "world": "2157年，人类在火星发现古代文明遗迹「星门」，打开了通往银河系各地的通道。各大势力争夺星门控制权。",
    "genre": "科幻 / 冒险",
    "scene": "火星轨道站「回声号」舰桥",
    "main_goal": "找到星门的真正起源，阻止各方势力引爆星际战争",
    "chars_json": json.dumps([
        {"name": "林夜", "isMain": True, "role_tags": ["调查船船长", "前特种部队"], "personality_tags": ["冷静", "果断", "内敛"], "appearance": "黑发灰瞳，左脸有一道旧伤疤", "relationship": ["自身"], "goal": "揭开星门之谜", "secret": "曾在特种部队执行过涉及星门的黑色行动", "background": "前地球联邦军特种部队，因一次任务失败被降职", "special_ability": "战术分析与危机应变"},
        {"name": "艾琳", "isMain": False, "role_tags": ["考古语言学家", "星门研究员"], "personality_tags": ["热情", "好奇", "敏感"], "appearance": "银白长发，紫色眼瞳，佩戴古代文字解码器", "relationship": ["同事", "暗恋对象"], "goal": "解码星门文字，证明古文明的存在", "secret": "体内植入了星门碎片，能与遗迹产生共鸣", "background": "联盟科学院最年轻的研究员"},
        {"name": "白璃", "isMain": False, "role_tags": ["情报商人", "自由航行者"], "personality_tags": ["狡猾", "幽默", "重情义"], "appearance": "红色短发，左耳三个耳环", "relationship": ["朋友", "情报来源"], "goal": "赚够钱买下自己的飞船", "secret": "曾是帝国情报局特工，叛逃后隐姓埋名", "background": "在星际黑市中长大"},
    ]),
    "rel_system": json.dumps({"stages": ["崩坏","敌视","对立","冷漠","疏远","陌生","认识","信赖","盟友","羁绊"], "affection": 30}),
    "factions_json": json.dumps([
        {"name": "地球联邦", "type": "government", "description": "人类母星政府，掌控星门安保", "goals": ["垄断星门控制权", "压制分离势力"], "resources": ["联邦舰队", "星门安保系统"], "controlledTerritories": ["火星轨道", "联邦首都"], "subordinateOrganizations": ["联邦舰队司令部", "星门管理局"], "keyAssets": ["星门主控站", "联邦舰队"], "power": {"military":80,"economic":70,"political":85,"technology":60}, "influence":85, "relation_to_player":"hostile", "leader":"卡尔森上将"},
        {"name": "自由航行者联盟", "type": "guild", "description": "独立飞船船长的互助组织，反对政府垄断", "goals": ["打破星门垄断", "建立自由通商区"], "resources": ["商船队", "情报网"], "controlledTerritories": ["自由港", "小行星带据点"], "subordinateOrganizations": ["商船工会", "走私网络"], "keyAssets": ["自由港", "加密通讯网"], "power": {"military":30,"economic":50,"political":40,"technology":55}, "influence":55, "relation_to_player":"ally", "leader":"白璃"},
        {"name": "古代守护者", "type": "religion", "description": "崇拜星门建造者的神秘组织，认为凡人不应触碰神圣遗产", "goals": ["封印所有星门", "消灭亵渎者"], "resources": ["信徒网络", "古代科技"], "controlledTerritories": ["地下神殿", "被遗忘的卫星"], "subordinateOrganizations": ["圣殿骑士团", "先知议会"], "keyAssets": ["古代圣物", "封印仪式"], "power": {"military":45,"economic":20,"political":30,"technology":90}, "influence":65, "relation_to_player":"enemy", "leader":"大祭司"},
    ]),
    "artifacts_json": json.dumps([
        {"name": "星门主钥", "type": "world", "description": "传说中能完全控制星门网络的古代装置", "ownerType":"none", "ownerId":"", "importance":95, "abilities":["控制星门","关闭通道","打开新通道"], "tags":["古代遗物","争夺目标"]},
        {"name": "解码石板", "type": "personal", "description": "刻有古代文字的金属板，艾琳的研究核心", "ownerType":"character", "ownerId":"艾琳", "importance":80, "abilities":["解读古代文字","定位遗迹"], "tags":["研究工具","线索"]},
    ]),
    "custom_rules": json.dumps({"stats":[{"key":"trust","label":"信任度","max":100},{"key":"influence","label":"影响力","max":100},{"key":"knowledge","label":"星门知识","max":100}]}),
})
check("创建故事", r.status_code in (200, 303))
time.sleep(2)

# ── 2. 开始游戏 ──
print("\n🎮 2. 开始游戏（AI生成开篇）...")
r = post("/api/start")
data = r.json()
check("开始游戏", not data.get("error") and len(data.get("story","")) > 50)
if data.get("error"):
    print(f"    错误: {data['error']}")
    sys.exit(1)
print(f"    轮次: {data['state']['turn']}, 状态: {data['state']['status']}")
print(f"    故事: {data['story'][:80]}...")
print(f"    选项: {len(data['options'])} 个")
char_count = len(data['state'].get('characters', {}))
print(f"    角色数: {char_count}")
time.sleep(3)

# ── 3. 进行5轮选择 ──
choices = ["A", "B", "A", "D", "B"]
for i, choice in enumerate(choices):
    print(f"\n🔄 第{i+2}轮 (选择 {choice})...")
    r = post("/api/next", {"choice": choice})
    data = r.json()
    ok = not data.get("error") and len(data.get("story","")) > 20
    check(f"第{i+2}轮", ok)
    if data.get("error"):
        print(f"    错误: {data['error']}")
        errors += 1
        continue
    print(f"    轮次: {data['state']['turn']}, 状态: {data['state']['status']}")
    char_count = len(data['state'].get('characters', {}))
    fac_count = len(data['state'].get('factions', []))
    print(f"    角色: {char_count}, 势力: {fac_count}")
    time.sleep(3)

# ── 4. 2轮自定义输入 ──
customs = ["调查星门控制站的异常信号", "与艾琳讨论星门碎片的共鸣现象"]
for custom in customs:
    print(f"\n✏️ 自定义输入: 「{custom}」...")
    r = post("/api/next", {"choice": custom})
    data = r.json()
    ok = not data.get("error") and len(data.get("story","")) > 20
    check(f"自定义: {custom[:20]}", ok)
    if data.get("error"):
        print(f"    错误: {data['error']}")
        errors += 1
        continue
    print(f"    轮次: {data['state']['turn']}, 状态: {data['state']['status']}")
    time.sleep(3)

# ── 5. 检查数据完整性 ──
print("\n📊 ===== 数据完整性检查 =====")

# 5a. Game state
state = get_json("/api/game-state")
check("游戏状态API正常", not state.get("error") and state.get("turn", 0) >= 7)
print(f"    总轮次: {state.get('state',{}).get('turn',0)}")
print(f"    角色数: {len(state.get('state',{}).get('characters',{}))}")

# 5b. NPCs
npcs = get_json("/api/npcs")
check("NPC列表API正常", len(npcs.get("characters",[])) >= 3)
for c in npcs.get("characters", []):
    trust = c.get("trust_pct", 50)
    faction = c.get("faction", "")
    print(f"    {c['name']}: trust={trust}%, faction={faction}, flags={len(c.get('flags',[]))}个")

# 5c. Dashboard
dash = get_json("/api/dashboard")
check("仪表盘API正常", not dash.get("error"))
print(f"    轮次={dash.get('turn',0)}, 角色={dash.get('character_count',0)}, 节点={dash.get('node_count',0)}")
analytics = dash.get("analytics", {})

# 5d. Memory
import yaml
from pathlib import Path
memory_path = Path("prompt-os-engine/data/memory.json")
if memory_path.exists():
    memory = json.loads(memory_path.read_text(encoding="utf-8"))
    chars = memory.get("characters", {})
    check("memory.json角色>0", len(chars) >= 2)
    for name, data in chars.items():
        trust = data.get("trust", 0.5)
        tier = data.get("tier", "?")
        flags = len(data.get("flags", []))
        print(f"    {name}: trust={trust:.2f}, tier={tier}, flags={flags}")
    
    factions_mem = memory.get("factions", {})
    check("memory.json有势力", len(factions_mem) >= 2)
    for fname, fdata in factions_mem.items():
        rep = fdata.get("reputation", 0.5)
        print(f"    [{fname}] 声望={rep:.2f}")
    
    arts = memory.get("artifacts", {})
    check("memory.json有物品", len(arts) >= 1)
    for aname, adata in arts.items():
        print(f"    [{aname}] 持有者={adata.get('ownerId','?')} 状态={adata.get('status','?')}")

# 5e. Session state
state_path = Path("prompt-os-engine/session_state.yaml")
if state_path.exists():
    with open(state_path, encoding="utf-8") as f:
        session = yaml.safe_load(f)
    hist = session.get("history", [])
    check("session有>=7条历史", len(hist) >= 7)
    check("session有角色", len(session.get("characters", {})) >= 2)
    print(f"    历史: {len(hist)}条, 角色: {len(session.get('characters',{}))}")

# 5f. World pack
wp_path = Path("prompt-os-engine/world_pack.yaml")
if wp_path.exists():
    with open(wp_path, encoding="utf-8") as f:
        wp = yaml.safe_load(f)
    w = wp.get("world", {})
    check("world_pack有势力", len(w.get("factions", [])) >= 2)
    check("world_pack有物品", len(w.get("artifacts", [])) >= 1)
    check("world_pack有角色", len(w.get("characters", [])) >= 3)

# ── 总结 ──
print(f"\n{'='*40}")
if errors == 0:
    print("✅ 全部检查通过！")
else:
    print(f"⚠️ 有 {errors} 个错误")
print(f"{'='*40}")
