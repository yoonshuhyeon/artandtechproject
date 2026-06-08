let socket = null;
let myId = null;
let myNickname = "";
let myGender = "M";

// 데이터 정의
const QUESTION_DATA = {
    'light': ["요즘 가장 빠져있는 것은?", "어릴 때 꿈은 뭐였어요?", "최근에 가장 웃겼던 일은?", "스트레스는 어떻게 푸세요?", "인생 영화나 드라마는?"],
    'deep': ["가장 소중하게 생각하는 가치관은?", "삶에서 가장 힘들었던 순간은?", "나의 가장 큰 장점과 단점은?", "10년 뒤 나의 모습은?", "사랑이란 무엇이라고 생각하세요?"],
    'fun': ["내가 만약 투명인간이 된다면?", "로또 1등 되면 가장 먼저 하고 싶은 것?", "무인도에 가져갈 세 가지?", "어제 밤에 꾼 꿈 이야기", "자신만의 특이한 습관"]
};

const GAME_CARDS = [
    "연애에서 가장 중요하다고 생각하는 것은?",
    "상대방의 첫인상은 어땠나요?",
    "나만 아는 맛집이 있다면?",
    "최근에 가장 즐겨 듣는 노래는?",
    "자신만의 스트레스 해소법은?"
];

let currentGameCardIndex = 0;
let myLikingScore = 0;

// 1. 화면 전환 및 초기화
function showView(viewId) {
    document.querySelectorAll('.view').forEach(v => v.classList.add('hidden'));
    document.getElementById(viewId).classList.remove('hidden');
    window.scrollTo(0, 0);

    // 특정 뷰 진입 시 초기화 로직
    if (viewId === 'question-view') loadQuestions('light');
    if (viewId === 'game-detail-view') updateGameCard();
}

// 2. 성별 및 탭 기능
function setGender(gender, element) {
    myGender = gender;
    element.parentElement.querySelectorAll('.tab-item').forEach(t => t.classList.remove('active'));
    element.classList.add('active');
}

function loadQuestions(category) {
    const container = document.getElementById('question-list-container');
    if (!container) return;
    
    container.innerHTML = QUESTION_DATA[category].map(q => `<div class="q-card" onclick="selectItem(this)">${q}</div>`).join('');
}

function selectItem(element) {
    element.parentElement.querySelectorAll('.q-card').forEach(c => {
        c.style.borderColor = "#F0F0F0";
        c.style.background = "#FDFDFD";
    });
    element.style.borderColor = "var(--primary-pink)";
    element.style.background = "#FFF5F8";
    element.dataset.selected = "true";
}

// 3. 추천 질문 탭 전환
document.querySelectorAll('#question-view .tab-item').forEach((tab, idx) => {
    tab.onclick = () => {
        document.querySelectorAll('#question-view .tab-item').forEach(t => t.classList.remove('active'));
        tab.classList.add('active');
        const categories = ['light', 'deep', 'fun'];
        loadQuestions(categories[idx]);
    };
});

// 4. 게임 카드 기능
function updateGameCard() {
    const card = document.querySelector('.game-card-item');
    card.innerText = GAME_CARDS[currentGameCardIndex];
}

window.nextGameCard = () => {
    currentGameCardIndex = (currentGameCardIndex + 1) % GAME_CARDS.length;
    updateGameCard();
};

window.prevGameCard = () => {
    currentGameCardIndex = (currentGameCardIndex - 1 + GAME_CARDS.length) % GAME_CARDS.length;
    updateGameCard();
};

// 5. 호감도 하트 기능
window.setLiking = (score) => {
    myLikingScore = score;
    const hearts = document.querySelectorAll('.heart');
    hearts.forEach((h, idx) => {
        if (idx < score) h.classList.add('filled');
        else h.classList.remove('filled');
    });
};

// 6. SOS 및 기타 전송 기능
window.sendRequest = (type) => {
    alert(`${type} 요청을 보냈습니다. 도우미가 처리 중입니다!`);
    showView('dashboard-view');
};

// 7. 입장 및 통신 로직
document.getElementById('join-btn').addEventListener('click', () => {
    const roomCode = document.getElementById('room-code').value.trim().toUpperCase();
    myNickname = document.getElementById('nickname').value.trim();

    if (!roomCode || !myNickname) {
        alert("룸 코드와 닉네임을 입력해주세요!");
        return;
    }

    connectWebSocket(roomCode);
});

function connectWebSocket(roomCode) {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const host = window.location.host;
    socket = new WebSocket(`${protocol}//${host}/ws/${roomCode}`);

    socket.onopen = () => {
        socket.send(JSON.stringify({ type: "join", nickname: myNickname, gender: myGender }));
    };

    socket.onmessage = (event) => {
        const data = JSON.parse(event.data);
        if (data.type === "state") showView('match-confirm-view');
        if (data.type === "presence") updateParticipantList(data.participants);
        if (data.type === "final_result") {
            document.getElementById('result-text').innerText = data.message;
            document.getElementById('result-modal').classList.remove('hidden');
        }
    };
}

function updateParticipantList(participants) {
    const listContainer = document.getElementById('participant-list');
    const waitMsg = document.getElementById('wait-msg');
    if (!listContainer) return;

    listContainer.innerHTML = "";
    const opponents = participants.filter(p => p.gender !== myGender);

    if (opponents.length === 0) waitMsg.classList.remove('hidden');
    else {
        waitMsg.classList.add('hidden');
        opponents.forEach(p => {
            const card = document.createElement('div');
            card.className = "menu-card";
            card.style.flexDirection = "column";
            card.innerHTML = `<div class="menu-icon" style="margin-right:0; margin-bottom:10px;">👤</div><div class="menu-title">${p.name}</div>`;
            card.onclick = () => {
                document.querySelectorAll('#participant-list .menu-card').forEach(c => c.style.borderColor = "#F8F8F8");
                card.style.borderColor = "var(--primary-pink)";
                socket.send(JSON.stringify({ type: "pick", target_id: p.id }));
            };
            listContainer.appendChild(card);
        });
    }
}

document.getElementById('close-modal-btn').onclick = () => document.getElementById('result-modal').classList.add('hidden');
