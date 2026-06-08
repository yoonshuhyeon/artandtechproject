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

# ==========================================
# 데이터 저장소 (Vercel에서는 인스턴스 초기화 시 초기화됨)
# 실운영에서는 Redis나 DB 사용 권장
# ==========================================
@dataclass
class RoomState:
    code: str
    location: str = ""
    meeting_time: str = ""
    reservation_name: str = ""
    participants: dict[str, dict] = field(default_factory=dict)
    picks: dict[str, str] = field(default_factory=dict)
    result_message: str = ""

ROOMS: dict[str, RoomState] = {}

@app.get("/")
async def read_index():
    return FileResponse(os.path.join(static_path, "index.html"))

@app.post("/api/create")
async def create_room(data: dict):
    room_code = data.get("room_code", "").upper()
    if not room_code:
        room_code = uuid.uuid4().hex[:4].upper()
    
    if room_code in ROOMS:
        raise HTTPException(status_code=400, detail="이미 존재하는 방 코드입니다.")
    
    ROOMS[room_code] = RoomState(
        code=room_code,
        location=data.get("location", "장소 미정"),
        meeting_time=data.get("meeting_time", "시간 미정"),
        reservation_name=data.get("reservation_name", "")
    )
    return {"room_code": room_code}

@app.post("/api/join/{room_code}")
async def join_room(room_code: str, data: dict):
    room_code = room_code.upper()
    if room_code not in ROOMS:
        raise HTTPException(status_code=404, detail="방을 찾을 수 없습니다.")
    
    room = ROOMS[room_code]
    
    gender = data.get("gender", "M")
    nickname = data.get("nickname", "익명").strip()
    
    # 닉네임 중복 체크
    for p in room.participants.values():
        if p['name'] == nickname:
            raise HTTPException(status_code=400, detail="이미 사용 중인 닉네임입니다.")
            
    client_id = uuid.uuid4().hex[:4]
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
    
    # 모든 인원이 투표했을 때 매칭 시작 (최소 2명 이상)
    if len(room.picks) >= len(room.participants) and len(room.participants) > 1:
        males = [p for p in room.participants.values() if p['gender'] == 'M']
        females = [p for p in room.participants.values() if p['gender'] == 'F']
        
        matched_males = set()
        matched_females = set()
        final_pairs = []

        # 1순위: 서로 지목 (Mutual)
        for f in females:
            f_id = f['id']
            m_id = room.picks.get(f_id)
            if m_id and room.picks.get(m_id) == f_id:
                if f_id not in matched_females and m_id not in matched_males:
                    final_pairs.append((f_id, m_id))
                    matched_females.add(f_id)
                    matched_males.add(m_id)

        # 2순위 & 3순위: 여자 우선 및 남자 몰림 처리
        # 남은 여자들이 선택한 남자별로 그룹화
        target_to_females = {}
        for f in females:
            f_id = f['id']
            if f_id in matched_females: continue
            m_id = room.picks.get(f_id)
            if m_id and m_id not in matched_males:
                if m_id not in target_to_females:
                    target_to_females[m_id] = []
                target_to_females[m_id].append(f_id)

        for m_id, f_ids in target_to_females.items():
            if m_id in matched_males: continue
            
            if len(f_ids) == 1:
                # 단독 지목 -> 여자 우선 매칭
                f_id = f_ids[0]
                final_pairs.append((f_id, m_id))
                matched_females.add(f_id)
                matched_males.add(m_id)
            else:
                # 몰림 발생 -> 남자의 선택을 확인 (3순위: 남자 우선)
                m_pick = room.picks.get(m_id)
                if m_pick in f_ids:
                    # 남자가 자신을 지목한 여자 중 한 명을 지목했으면 그 여자와 매칭
                    final_pairs.append((m_pick, m_id))
                    matched_females.add(m_pick)
                    matched_males.add(m_id)
                else:
                    # 남자가 다른 사람을 지목했거나 안 했으면, 지목한 여자 중 랜덤 1명
                    selected_f = random.choice(f_ids)
                    final_pairs.append((selected_f, m_id))
                    matched_females.add(selected_f)
                    matched_males.add(m_id)

        # 4순위: 나머지 랜덤 매칭
        remaining_f = [f['id'] for f in females if f['id'] not in matched_females]
        remaining_m = [m['id'] for m in males if m['id'] not in matched_males]
        random.shuffle(remaining_f)
        random.shuffle(remaining_m)
        
        extra_pairs = list(zip(remaining_f, remaining_m))
        for f, m in extra_pairs:
            final_pairs.append((f, m))

        # 결과 메시지 생성
        prompt = random.choice(PROMPTS)
        msg = f"🎉 설렘 가득! 오늘의 자리 배치 🎉\n미션: {prompt}\n\n"
        for f, m in final_pairs:
            msg += f"✨ {room.participants[f]['name']} ❤️ {room.participants[m]['name']}\n"
        
        if not final_pairs:
            msg = "인원 부족으로 매칭을 진행할 수 없어요! 😢"

        room.result_message = msg
        room.picks.clear() # 리셋

    return {"status": "ok"}

@app.get("/api/status/{room_code}")
async def get_status(room_code: str):
    room = ROOMS.get(room_code.upper())
    if not room: return {"participants": [], "result": ""}
    
    m_count = len([p for p in room.participants.values() if p['gender'] == 'M'])
    f_count = len([p for p in room.participants.values() if p['gender'] == 'F'])
    
    return {
        "participants": list(room.participants.values()),
        "result": room.result_message,
        "location": room.location,
        "meeting_time": room.meeting_time,
        "reservation_name": room.reservation_name,
        "m_count": m_count,
        "f_count": f_count
    }
