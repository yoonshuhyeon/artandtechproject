from __future__ import annotations
import random
import time
import uuid
import os
from dataclasses import dataclass, field
from typing import Any
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

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

# 정적 파일 설정
base_path = os.path.dirname(os.path.dirname(__file__))
static_path = os.path.join(base_path, "static")
image_path = os.path.join(base_path, "앱구성")

app.mount("/static", StaticFiles(directory=static_path), name="static")
app.mount("/앱구성", StaticFiles(directory=image_path), name="앱구성")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==========================================
# 데이터 저장소 (Vercel에서는 인스턴스 초기화 시 초기화됨)
# 실운영에서는 Redis나 DB 사용 권장
# ==========================================
@dataclass
class RoomState:
    code: str
    participants: dict[str, dict] = field(default_factory=dict)
    picks: dict[str, str] = field(default_factory=dict)
    result_message: str = ""

ROOMS: dict[str, RoomState] = {}

@app.get("/")
async def read_index():
    return FileResponse(os.path.join(static_path, "index.html"))

@app.post("/api/join/{room_code}")
async def join_room(room_code: str, data: dict):
    room_code = room_code.upper()
    if room_code not in ROOMS:
        ROOMS[room_code] = RoomState(code=room_code)
    
    room = ROOMS[room_code]
    client_id = uuid.uuid4().hex[:4]
    
    gender = data.get("gender", "M")
    nickname = data.get("nickname", "익명").strip()
    team = "남성" if gender == "M" else "여성"
    
    room.participants[client_id] = {
        "id": client_id, 
        "team": team, 
        "name": nickname, 
        "gender": gender
    }
    
    return {"client_id": client_id, "room_code": room_code}

@app.post("/api/pick/{room_code}/{client_id}")
async def pick_partner(room_code: str, client_id: str, data: dict):
    room = ROOMS.get(room_code.upper())
    if not room: raise HTTPException(status_code=404, detail="Room not found")
    
    target_id = data.get("target_id")
    room.picks[client_id] = target_id
    
    # 매칭 로직 (모두 투표 시 결과 생성)
    if len(room.picks) >= len(room.participants) and len(room.participants) > 1:
        # (기존 매칭 로직과 동일)
        males = [p for p in room.participants.values() if p['gender'] == 'M']
        females = [p for p in room.participants.values() if p['gender'] == 'F']
        final_pairs = []
        
        # 간단 매칭 예시
        f_ids = [p['id'] for p in females]
        m_ids = [p['id'] for p in males]
        random.shuffle(f_ids); random.shuffle(m_ids)
        
        pairs = list(zip(f_ids, m_ids))
        prompt = random.choice(PROMPTS)
        msg = f"🎉 오늘의 자리 배치 발표! 🎉\n미션: {prompt}\n\n"
        for f, m in pairs:
            msg += f"✨ {room.participants[f]['name']} X {room.participants[m]['name']}\n"
        
        room.result_message = msg
        room.picks.clear() # 다음 게임을 위해 리셋

    return {"status": "ok"}

@app.get("/api/status/{room_code}")
async def get_status(room_code: str):
    room = ROOMS.get(room_code.upper())
    if not room: return {"participants": [], "result": ""}
    
    return {
        "participants": list(room.participants.values()),
        "result": room.result_message
    }
