let myId = null;
let myNickname = "";
let myGender = "M";
let currentRoomCode = "";
let pollInterval = null;

// (QUESTION_DATA, GAME_CARDS 등 기존 데이터는 그대로 유지)
const QUESTION_DATA = {
    'light': ["요즘 가장 빠져있는 것은?", "어릴 때 꿈은 뭐였어요?", "최근에 가장 웃겼던 일은?", "스트레스는 어떻게 푸세요?", "인생 영화나 드라마는?"],
    'deep': ["가장 소중하게 생각하는 가치관은?", "삶에서 가장 힘들었던 순간은?", "나의 가장 큰 장점과 단점은?", "10년 뒤 나의 모습은?", "사랑이란 무엇이라고 생각하세요?"],
    'fun': ["내가 만약 투명인간이 된다면?", "로또 1등 되면 가장 먼저 하고 싶은 것?", "무인도에 가져갈 세 가지?", "어제 밤에 꾼 꿈 이야기", "자신만의 특이한 습관"]
};
const GAME_CARDS = ["연애에서 가장 중요하다고 생각하는 것은?", "상대방의 첫인상은 어땠나요?", "나만 아는 맛집이 있다면?", "최근에 가장 즐겨 듣는 노래는?", "자신만의 스트레스 해소법은?"];
let currentGameCardIndex = 0;

function showView(viewId) {
    document.querySelectorAll('.view').forEach(v => v.classList.add('hidden'));
    document.getElementById(viewId).classList.remove('hidden');
    if (viewId === 'question-view') loadQuestions('light');
}

function setGender(gender, element) {
    myGender = gender;
    element.parentElement.querySelectorAll('.tab-item').forEach(t => t.classList.remove('active'));
    element.classList.add('active');
}

// 입장 로직 (HTTP POST)
document.getElementById('join-btn').addEventListener('click', async () => {
    currentRoomCode = document.getElementById('room-code').value.trim().toUpperCase();
    myNickname = document.getElementById('nickname').value.trim();

    if (!currentRoomCode || !myNickname) {
        alert("룸 코드와 닉네임을 입력해주세요!");
        return;
    }

    try {
        const res = await fetch(`/api/join/${currentRoomCode}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ nickname: myNickname, gender: myGender })
        });
        const data = await res.json();
        myId = data.client_id;
        
        showView('match-confirm-view');
        startPolling(); // 폴링 시작
    } catch (e) {
        alert("서버 연결에 실패했습니다.");
    }
});

// 폴링 로직 (2초마다 상태 확인)
function startPolling() {
    if (pollInterval) clearInterval(pollInterval);
    pollInterval = setInterval(async () => {
        try {
            const res = await fetch(`/api/status/${currentRoomCode}`);
            const data = await res.json();
            
            updateParticipantList(data.participants);
            
            if (data.result) {
                document.getElementById('result-text').innerText = data.result;
                document.getElementById('result-modal').classList.remove('hidden');
            }
        } catch (e) {
            console.error("Polling error", e);
        }
    }, 2000);
}

async function selectPartner(targetId, cardElement) {
    document.querySelectorAll('#participant-list .menu-card').forEach(c => c.style.borderColor = "#F8F8F8");
    cardElement.style.borderColor = "var(--primary-pink)";

    await fetch(`/api/pick/${currentRoomCode}/${myId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ target_id: targetId })
    });
}

function updateParticipantList(participants) {
    const listContainer = document.getElementById('participant-list');
    const waitMsg = document.getElementById('wait-msg');
    if (!listContainer) return;

    listContainer.innerHTML = "";
    const opponents = participants.filter(p => p.gender !== myGender);

    if (opponents.length === 0) {
        waitMsg.classList.remove('hidden');
    } else {
        waitMsg.classList.add('hidden');
        opponents.forEach(p => {
            const card = document.createElement('div');
            card.className = "menu-card";
            card.style.flexDirection = "column";
            card.innerHTML = `<div class="menu-icon" style="margin-right:0; margin-bottom:10px;">👤</div><div class="menu-title">${p.name}</div>`;
            card.onclick = () => selectPartner(p.id, card);
            listContainer.appendChild(card);
        });
    }
}

// (나머지 헬퍼 함수들 - loadQuestions, nextGameCard 등은 동일하게 유지)
function loadQuestions(category) {
    const container = document.getElementById('question-list-container');
    if (!container) return;
    container.innerHTML = QUESTION_DATA[category].map(q => `<div class="q-card" onclick="selectItem(this)">${q}</div>`).join('');
}
function selectItem(element) {
    element.parentElement.querySelectorAll('.q-card').forEach(c => { c.style.borderColor = "#F0F0F0"; c.style.background = "#FDFDFD"; });
    element.style.borderColor = "var(--primary-pink)";
    element.style.background = "#FFF5F8";
}
window.nextGameCard = () => { currentGameCardIndex = (currentGameCardIndex + 1) % GAME_CARDS.length; document.querySelector('.game-card-item').innerText = GAME_CARDS[currentGameCardIndex]; };
window.prevGameCard = () => { currentGameCardIndex = (currentGameCardIndex - 1 + GAME_CARDS.length) % GAME_CARDS.length; document.querySelector('.game-card-item').innerText = GAME_CARDS[currentGameCardIndex]; };
window.setLiking = (score) => { document.querySelectorAll('.heart').forEach((h, idx) => { if (idx < score) h.classList.add('filled'); else h.classList.remove('filled'); }); };
window.sendRequest = (type) => { alert(`${type} 요청을 보냈습니다.`); showView('dashboard-view'); };
document.getElementById('close-modal-btn').onclick = () => document.getElementById('result-modal').classList.add('hidden');
