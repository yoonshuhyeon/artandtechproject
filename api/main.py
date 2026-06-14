import os
import json
import random
import uuid
from dataclasses import dataclass, field, asdict
from typing import Any, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from upstash_redis import Redis

# ==========================================
# Redis 설정
# ==========================================
UPSTASH_REDIS_REST_URL = os.environ.get("UPSTASH_REDIS_REST_URL")
UPSTASH_REDIS_REST_TOKEN = os.environ.get("UPSTASH_REDIS_REST_TOKEN")

redis = None
if UPSTASH_REDIS_REST_URL and UPSTASH_REDIS_REST_TOKEN:
    redis = Redis(url=UPSTASH_REDIS_REST_URL, token=UPSTASH_REDIS_REST_TOKEN)

# ==========================================
# 데이터 모델
# ==========================================
@dataclass
class RoomState:
    code: str
    location: str = ""
    meeting_time: str = ""
    reservation_name: str = ""
    target_count: int = 0  # 목표 인원수 추가
    participants: dict[str, dict] = field(default_factory=dict)
    picks: dict[str, str] = field(default_factory=dict)
    result_message: str = ""
    is_matching_complete: bool = False
    host_id: str = ""

LOCAL_ROOMS: dict[str, Any] = {}

def get_room(room_code: str) -> Optional[RoomState]:
    room_code = room_code.upper()
    if redis:
        data = redis.get(f"room:{room_code}")
        if data:
            if isinstance(data, str): data = json.loads(data)
            return RoomState(**data)
    else:
        data = LOCAL_ROOMS.get(room_code)
        if data: return RoomState(**data)
    return None

def save_room(room: RoomState):
    room_dict = asdict(room)
    if redis:
        redis.set(f"room:{room.code}", json.dumps(room_dict))
        redis.expire(f"room:{room.code}", 86400)
    else:
        LOCAL_ROOMS[room.code] = room_dict

def delete_room_data(room_code: str):
    if redis:
        redis.delete(f"room:{room_code.upper()}")
    else:
        if room_code.upper() in LOCAL_ROOMS:
            del LOCAL_ROOMS[room_code.upper()]

# ==========================================
# 질문 데이터
# ==========================================
PROMPTS: list[str] = [
    "밸런스 게임: 애인 연락 빈도 (하루 1번 vs 틈날 때마다)",
    "지금 이 자리에서 한 명만 초능력 얻는다면 누구?",
    "밸런스 게임: 첫 데이트 (조용한 카페 vs 시끌벅적 포차)",
    "가장 최근에 소소하게 행복했던 순간은?",
    "오늘 서로 별명 하나씩 지어주기",
    "인생 영화나 드라마 하나씩 추천하기",
    "스트레스 해소법 공유하기!",
    "어릴 때 꿈은 무엇이었나요?"
]

app = FastAPI(title="atc-backend", version="0.1.0")

base_path = os.path.dirname(os.path.dirname(__file__))
static_path = os.path.join(base_path, "static")
image_path = os.path.join(base_path, "assets")

if os.path.exists(static_path):
    app.mount("/static", StaticFiles(directory=static_path), name="static")
if os.path.exists(image_path):
    app.mount("/assets", StaticFiles(directory=image_path), name="assets")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def read_index():
    return FileResponse(os.path.join(static_path, "index.html"))

@app.post("/api/create")
async def create_room(data: dict):
    room_code = data.get("room_code", "").upper()
    if not room_code: room_code = uuid.uuid4().hex[:4].upper()
    if get_room(room_code): raise HTTPException(status_code=400, detail="이미 존재하는 방 코드입니다.")
    
    target_count = 0
    try:
        target_count = int(data.get("target_count", 0))
    except: pass

    new_room = RoomState(
        code=room_code, 
        location=data.get("location", "장소 미정"), 
        meeting_time=data.get("meeting_time", "시간 미정"), 
        reservation_name=data.get("reservation_name", ""),
        target_count=target_count
    )
    save_room(new_room)
    return {"room_code": room_code}

@app.post("/api/join/{room_code}")
async def join_room(room_code: str, data: dict):
    room = get_room(room_code)
    if not room: raise HTTPException(status_code=404, detail="방을 찾을 수 없습니다.")
    gender, nickname = data.get("gender", "M"), data.get("nickname", "익명").strip()
    for p in room.participants.values():
        if p['name'] == nickname: raise HTTPException(status_code=400, detail="이미 사용 중인 닉네임입니다.")
    client_id = uuid.uuid4().hex[:4]
    if not room.host_id:
        room.host_id = client_id
    room.participants[client_id] = {"id": client_id, "team": "남성" if gender == "M" else "여성", "name": nickname, "gender": gender}
    save_room(room)
    return {"client_id": client_id, "room_code": room.code}

@app.delete("/api/room/{room_code}/{host_id}")
async def delete_room(room_code: str, host_id: str):
    room = get_room(room_code)
    if not room: raise HTTPException(status_code=404, detail="Room not found")
    if room.host_id != host_id: raise HTTPException(status_code=403, detail="방장만 방을 폭파할 수 있습니다.")
    delete_room_data(room_code)
    return {"status": "ok"}

@app.delete("/api/kick/{room_code}/{host_id}/{target_id}")
async def kick_member(room_code: str, host_id: str, target_id: str):
    room = get_room(room_code)
    if not room: raise HTTPException(status_code=404, detail="Room not found")
    if room.host_id != host_id: raise HTTPException(status_code=403, detail="방장만 멤버를 내보낼 수 있습니다.")
    if target_id in room.participants:
        del room.participants[target_id]
        if target_id in room.picks: del room.picks[target_id]
        save_room(room)
        return {"status": "ok"}
    raise HTTPException(status_code=404, detail="대상 멤버를 찾을 수 없습니다.")

@app.post("/api/pick/{room_code}/{client_id}")
async def pick_partner(room_code: str, client_id: str, data: dict):
    room = get_room(room_code)
    if not room: raise HTTPException(status_code=404, detail="Room not found")
    if room.is_matching_complete: return {"status": "already_completed"}
    room.picks[client_id] = data.get("target_id")
    if len(room.picks) >= len(room.participants) and len(room.participants) > 1:
        males = [p for p in room.participants.values() if p['gender'] == 'M']
        females = [p for p in room.participants.values() if p['gender'] == 'F']
        matched_males, matched_females, final_pairs = set(), set(), []
        for f in females:
            f_id = f['id']
            m_id = room.picks.get(f_id)
            if m_id and room.picks.get(m_id) == f_id:
                if f_id not in matched_females and m_id not in matched_males:
                    final_pairs.append((f_id, m_id)); matched_females.add(f_id); matched_males.add(m_id)
        target_to_females = {}
        for f in females:
            f_id = f['id']
            if f_id in matched_females: continue
            m_id = room.picks.get(f_id)
            if m_id and m_id not in matched_males:
                if m_id not in target_to_females: target_to_females[m_id] = []
                target_to_females[m_id].append(f_id)
        for m_id, f_ids in target_to_females.items():
            if m_id in matched_males: continue
            if len(f_ids) == 1:
                f_id = f_ids[0]; final_pairs.append((f_id, m_id)); matched_females.add(f_id); matched_males.add(m_id)
            else:
                m_pick = room.picks.get(m_id)
                selected_f = m_pick if m_pick in f_ids else random.choice(f_ids)
                final_pairs.append((selected_f, m_id)); matched_females.add(selected_f); matched_males.add(m_id)
        remaining_f = [f['id'] for f in females if f['id'] not in matched_females]
        remaining_m = [m['id'] for m in males if m['id'] not in matched_males]
        random.shuffle(remaining_f); random.shuffle(remaining_m)
        for f, m in list(zip(remaining_f, remaining_m)): final_pairs.append((f, m))
        prompt = random.choice(PROMPTS)
        msg = f"🎉 설렘 가득! 오늘의 자리 배치 🎉\n\n"
        for f, m in final_pairs: msg += f"✨ {room.participants[f]['name']} ❤️ {room.participants[m]['name']}\n"
        room.result_message = msg + f"\n💡 미션: {prompt}"
        room.is_matching_complete = True
    save_room(room)
    return {"status": "ok"}

@app.post("/api/reset-matching/{room_code}")
async def reset_matching(room_code: str):
    room = get_room(room_code)
    if not room: raise HTTPException(status_code=404, detail="Room not found")
    room.picks.clear(); room.result_message = ""; room.is_matching_complete = False
    save_room(room)
    return {"status": "reset_ok"}

@app.get("/api/status/{room_code}")
async def get_status(room_code: str):
    room = get_room(room_code)
    if not room: return {"participants": [], "result": "ROOM_DELETED"} # 방 삭제 시 시그널
    m_count = len([p for p in room.participants.values() if p['gender'] == 'M'])
    f_count = len([p for p in room.participants.values() if p['gender'] == 'F'])
    return {
        "participants": list(room.participants.values()), "result": room.result_message,
        "is_matching_complete": room.is_matching_complete, "location": room.location,
        "meeting_time": room.meeting_time, "reservation_name": room.reservation_name,
        "target_count": room.target_count,
        "m_count": m_count, "f_count": f_count, "host_id": room.host_id
    }
