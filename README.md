# 천운(HavenlyLuck) Backend

천운 서비스의 API 서버입니다. 응모(래플), 쿠지(제비뽑기), 상점, 보관함·배송, 쌀포인트, 후기·문의, 관리자 기능을 제공합니다.

- 사이트: https://havenlyluck.com (프론트엔드: [HavenlyLuck/Frontend](https://github.com/HavenlyLuck/Frontend))
- 스택: Python · FastAPI · SQLAlchemy 2 · Alembic · MySQL(PyMySQL)
- 외부 서비스: 포트원 V2(본인인증·카드 결제), Cloudinary(이미지), 도로명주소 API, 스마트택배(배송 조회)
- 배포: `main` 브랜치에 push하면 GitHub Actions가 Azure Web App(`havenlyluck`)에 배포합니다.

---

## 빠른 시작

Python 3.9 이상이 필요합니다. 로컬은 3.9(`.python-version`), CI와 배포는 3.11로 돌아갑니다.

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# .env 작성 (아래 "환경 변수" 참고)

alembic upgrade head            # DB 테이블 만들기·갱신
uvicorn app.main:app --reload   # http://localhost:8000
```

- API 문서(Swagger): http://localhost:8000/docs
- 서버 상태 확인: `GET /server_ok`
- 프론트 로컬 주소(`http://localhost:3000`)와 같은 와이파이의 사설 IP(`http://192.168.x.x:3000` 등)는 CORS가 열려 있습니다. 허용 주소는 [app/main.py](app/main.py)에 있습니다.

> **주의:** `.env`의 DB가 운영 DB를 가리키면 `alembic upgrade`와 로컬 서버가 운영 데이터를 바로 바꿉니다. 로컬 개발은 따로 만든 DB로 하세요.

## 환경 변수

`.env`(git에 올리지 않음)에 넣습니다. 운영 값은 GitHub Secrets로 관리합니다.

| 이름 | 필수 | 설명 |
|---|---|---|
| `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME` | 필수 | MySQL 접속 정보 |
| `SECRET_KEY` | 필수 | JWT 서명 키 |
| `ALGORITHM` | | JWT 알고리즘 (기본 `HS256`) |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | | 액세스 토큰 유효 시간 (기본 60분) |
| `REFRESH_TOKEN_EXPIRE_MINUTES` | | 리프레시 토큰 유효 시간 (기본 14일) |
| `CLOUDINARY_CLOUD_NAME`, `CLOUDINARY_API_KEY`, `CLOUDINARY_API_SECRET` | 필수 | 상품·후기 이미지 업로드와 삭제 |
| `PORTONE_API_SECRET` | | 포트원 V2 API Secret. 없으면 본인인증과 결제가 동작하지 않음 |
| `PORTONE_STORE_ID` | | 포트원 상점 아이디(`store-xxxx`) |
| `JUSO_API_KEY` | | 도로명주소 검색 승인키. 없으면 주소 검색 비활성화 |
| `SWEETTRACKER_API_KEY` | | 스마트택배 배송 조회 키. 없으면 배송 조회 비활성화 |

서비스 규칙 값(응모 기간, 쿠지 최대 제비 수, 전환 모금 비율, 자동 추첨 대기 시간 등)은 코드 상수로 [app/core/config.py](app/core/config.py)에 모여 있습니다.

## 폴더 구조

```
app/
  main.py          FastAPI 앱, CORS, 라우터 등록, 서버 주기 작업(settle_loop)
  database.py      DB 엔진·세션 (격리 수준 READ COMMITTED)
  core/
    config.py      환경 변수와 서비스 규칙 상수
    security.py    비밀번호 해시(bcrypt), JWT 발급·검증
    dependencies.py  로그인 사용자·관리자 확인, 관리자 접속기록
    avatar_items.py  아바타 아이템 목록·가격 (프론트와 맞춰야 함)
  routers/         API 엔드포인트 (요청 검증 → crud 호출 → 응답)
  crud/            비즈니스 로직과 DB 처리
  models/          SQLAlchemy 모델 (테이블)
  schemas/         Pydantic 요청·응답 모델
  services/        외부 API 연동 (portone, cloudinary, juso, tracker)
alembic/versions/  DB 마이그레이션
```

라우터는 얇게 두고, 로직은 `crud/`에 둡니다. 외부 API는 `services/`에서만 부릅니다.

## 용어

| 용어 | 뜻 |
|---|---|
| 응모 (raffle) | 응모권을 사서 참여하고, 매진되면 응모권 수에 비례한 확률로 자동 추첨하는 상품 |
| 응모 번호 | 한 상품에 처음 응모할 때 받는 번호(1부터). 추가로 사도 같은 번호를 씀 |
| 쿠지 (kuji) | 제비판에서 번호를 골라 뽑는 상품. 상위상·하위상과, 마지막 제비를 뽑은 사람에게 주는 라스트원상이 있음 |
| 상점 (store) | 바로 사는 상품. `cash`(카드 결제)와 `ssal`(쌀포인트) 두 종류 |
| 전환 모금 (funding) | 상점 상품의 응모권이 1/3 팔리면 응모 상품으로 전환되는 기능 |
| 쌀포인트 | 낙첨 보상 등으로 받는 포인트. 쌀포인트 상점·아바타 아이템 구매에 씀 |
| 쌀 응모권 (무료 응모권) | 추천인 보상으로 받는 무료 응모권 (`free_tickets`) |
| 보관함 (storage) | 당첨·구매한 상품이 모이는 곳. 여기서 배송 신청함 |

## 핵심 흐름

### 인증

- 로그인하면 액세스 토큰(60분)과 리프레시 토큰(14일)을 줍니다. 요청에는 `Authorization: Bearer <액세스 토큰>`을 붙입니다.
- 권한은 세 단계입니다: 누구나 / 로그인(`get_current_user`) / 관리자(`get_current_admin`, `users.is_admin`).
- 회원가입은 포트원 본인인증이 필수입니다. 이름·휴대폰·생년월일은 클라이언트 값을 믿지 않고 서버가 포트원에서 직접 조회합니다. 만 14세 미만과 이미 가입된 번호는 거절합니다.

### 카드 결제 ([crud/payment.py](app/crud/payment.py))

응모권, 쿠지 제비, 결제 상점 상품은 모두 같은 결제 흐름을 탑니다.

1. `POST /payments/prepare`: 서버가 금액을 정해 `pending` 주문을 만듭니다. 프론트는 이 `payment_id`와 금액으로 포트원 결제창을 엽니다.
2. `POST /payments/{id}/complete`: 서버가 포트원에 결제를 직접 조회해서, `PAID`이고 금액이 같을 때만 상품을 지급합니다. 그 사이 매진됐으면 결제를 취소합니다. 여러 번 불러도 결과는 같습니다.
3. 주기 작업: 결제만 하고 창을 닫은 주문을 마저 처리하고, 환불 대기(`cancel_requested`) 결제를 포트원에 취소 요청합니다.

결제 상태: `pending` → `paid` / `failed` / `cancel_requested` → `cancelled`. 포트원이 취소를 거절하면 `cancel_failed`가 되고, 관리자가 직접 확인해야 합니다.

### 응모 ([crud/raffle.py](app/crud/raffle.py))

- 관리자가 등록하면 바로 열리고, 응모 기간은 1~3일 중에서 고릅니다.
- 응모권이 매진되면 1분 뒤(`RAFFLE_DRAW_DELAY_SECONDS`) 서버가 자동 추첨합니다. 응모권 1장이 당첨 확률 1칸이고, 난수는 `secrets`를 씁니다.
- 기간 안에 매진되지 않으면 취소되고, 결제는 전액 환불됩니다.
- 당첨 상품은 당첨자 보관함으로 들어갑니다. 낙첨자는 결제한 금액만큼 쌀포인트를 받습니다(무료 응모권으로 응모한 장수는 제외).
- 추천인을 등록한 회원이 첫 응모권을 사면, 그 회원과 추천해 준 회원이 각각 무료 응모권 1장을 받습니다.
- 응모자는 매진 전에 응모권 일부나 전부를 취소할 수 있습니다(부분 환불).
- 상태: `funding`(전환 모금 중) → `open` → `completed` / `cancelled`

### 서버 주기 작업 ([app/main.py](app/main.py) `settle_loop`)

API 요청 경로에서는 정산하지 않고, 서버 안의 백그라운드 루프가 처리합니다.

| 주기 | 작업 |
|---|---|
| 5초 | 기간 만료 응모 취소·환불, 매진 응모 자동 추첨 |
| 30초 | 결제 정리 (창 닫은 결제 지급, 환불 재시도) |
| 1시간 | 탈퇴 회원의 보존 기간 지난 정보 파기 |

서버 프로세스가 여러 개여도 행 잠금(`SELECT ... FOR UPDATE`) 때문에 한 번만 처리됩니다.

### 재고·정산 (관리자)

- 재고([crud/inventory.py](app/crud/inventory.py)): 입고 기록을 상품(응모·쿠지·상점)에 연결해 씁니다.
  - "판매 중"과 "판매 완료" 수량은 저장하지 않고, 연결된 상품 상태에서 계산합니다.
  - 그래서 응모 취소, 쿠지 판매 종료, 상점 수량 조정이 일어나면 남은 물건이 자동으로 재고로 돌아갑니다.
- 정산(`/finance`): 기간별 판매 기록, 부대비용, 입고 금액을 내려주고, 손익 합계는 화면에서 계산합니다.

### 개인정보 ([crud/withdrawal.py](app/crud/withdrawal.py))

개인정보처리방침(프론트 `/privacy`)과 맞춰 구현했습니다. 정책을 바꾸면 양쪽을 같이 고쳐야 합니다.

- **가입 동의:** 이용약관·만 14세 확인(필수)과 후기 홍보 활용(선택)의 동의 시각을 `users`에 저장합니다. 후기 홍보 동의는 `PUT /users/me/review-marketing`으로 철회할 수 있습니다.
- **회원 탈퇴 (`DELETE /users/me`):**
  - 진행 중인 응모, 결제·환불, 배송이 있으면 400과 이유를 돌려줍니다.
  - 탈퇴하면 `users` 행의 개인정보를 가명 값으로 바꿉니다. 결제 기록이 회원 행을 가리키고 있어서 행 자체는 남깁니다.
  - 법정 보존 정보는 `withdrawn_users`로 분리해 5년 보관합니다. 배송에 쓴 배송지도 5년 보관합니다.
  - 문의는 비공개로 바꿔 3년 보관합니다. 후기는 Cloudinary 사진까지 바로 지웁니다.
  - 쌀포인트, 쌀 응모권, 배송 신청 안 한 보관함 상품은 소멸합니다.
- **관리자 접속기록:** 관리자 API를 호출할 때마다 `admin_access_logs`에 관리자 id, 일시, IP, 작업, 경로를 남깁니다(최소 2년 보관). 기록을 못 남기면 요청을 503으로 막습니다. 일반 API에서 관리자 권한으로 개인정보를 다룰 때(비공개 문의 조회, 남의 후기 삭제)는 `log_admin_access()`를 직접 부릅니다.
- **비밀번호:** bcrypt로 해시해 저장합니다.

## API 목록

자세한 요청·응답 형식은 `/docs`(Swagger)에서 볼 수 있습니다. 🔒 로그인 필요, 🛠 관리자 전용.

| 경로 | 내용 |
|---|---|
| `/users` | 회원가입, 본인인증 확인, 로그인, 토큰 재발급, 중복 확인, 내 정보(🔒), 캐릭터 저장(🔒), 비밀번호 변경(🔒), 후기 홍보 동의(🔒), 회원 탈퇴(🔒) |
| `/raffles` | 응모 목록·상세, 내 응모·취소·무료 응모권 응모(🔒), 추첨 화면(🔒), 등록·취소·추첨 대기 목록·응모자 목록(🛠) |
| `/kuji` | 쿠지 목록·상세·제비판, 등록·판매 종료·관리자 목록(🛠) |
| `/store-products` | 상점 목록·상세, 쌀포인트 구매(🔒), 등록·수량 조정·삭제(🛠) |
| `/payments` | 결제 준비·완료, 구매 내역 (🔒) |
| `/storage` | 보관함, 배송 신청, 배송 조회, 구매 취소 (🔒), 배송 관리·발송 처리(🛠) |
| `/addresses` | 배송지 목록·등록·삭제·기본 지정, 도로명주소 검색 (🔒) |
| `/points` | 쌀포인트 잔액·내역 (🔒) |
| `/avatar-items` | 아바타 아이템 목록, 보유 목록·구매(🔒) |
| `/referrals` | 내 추천인 코드, 추천인 등록, 무료 응모권 목록 (🔒) |
| `/reviews` | 후기 목록, 작성·삭제·작성 가능한 상품(🔒) |
| `/inquiries` | 문의 목록, 작성(🔒), 관리자 목록·답변(🛠) |
| `/notices` | 공지 목록, 작성·수정·삭제(🛠) |
| `/inventory` | 재고 품목·입고 기록 (🛠) |
| `/finance` | 기간별 판매·비용 정산, 부대비용 등록·삭제 (🛠) |
| `/admin` | 관리자 권한 확인 (🛠) |

## DB 마이그레이션

모델을 바꾸면 Alembic 마이그레이션을 같이 만듭니다.

```bash
alembic revision -m "설명"   # alembic/versions/에 새 파일 생성 → upgrade/downgrade 작성
alembic upgrade head          # 적용
alembic heads                 # head가 하나인지 확인 (둘 이상이면 down_revision 정리)
```

- 기존 파일처럼 docstring에 무엇을 왜 바꾸는지 한국어로 적습니다.
- MySQL ENUM에 값을 추가할 때는 `op.alter_column(..., existing_type=Enum(옛 값), type_=Enum(새 값))` 패턴을 씁니다. 예시: [f2c8e4a6b1d9](alembic/versions/f2c8e4a6b1d9_add_consent_withdrawal_admin_logs.py)
- 배포 때 `alembic upgrade head`가 자동으로 실행됩니다. 실패하지 않도록 로컬 DB에서 먼저 돌려 보세요.

## 배포

[.github/workflows/deploy.yml](.github/workflows/deploy.yml)

- **PR:** flake8 문법 검사를 돌립니다.
- **main push(머지 포함):** 다음 순서로 진행됩니다.
  1. Azure Web App에 코드를 올립니다.
  2. 앱 환경 변수를 GitHub Secrets 값으로 설정합니다.
  3. `alembic upgrade head`를 실행합니다.
- 새 환경 변수를 추가하면 GitHub Secrets와 `deploy.yml`의 `app-settings-json`에 둘 다 넣어야 운영에 반영됩니다.

## 코드 작성 시 주의

- **Python 3.9 호환:** 로컬이 3.9라서 `str | None` 같은 문법은 함수 시그니처에서 에러가 납니다. `Optional[str]`을 쓰세요.
- **시간:** DB에는 UTC를 시간대 정보 없이(naive) 저장합니다. 한국 날짜가 필요한 곳(정산, 만 나이 계산)만 +9시간으로 바꿉니다.
- **동시성:** 재고, 응모권 수, 잔액처럼 동시에 바뀔 수 있는 값은 `with_for_update()`로 행을 잠근 뒤 다시 읽고 바꿉니다. 그래서 DB 격리 수준을 READ COMMITTED로 둡니다.
- **결제 금액:** 금액은 항상 서버가 정하고, 지급 전에 포트원 결제 금액과 비교합니다. 클라이언트가 보낸 금액·이름·전화번호는 믿지 않습니다.
- **아바타 아이템:** [app/core/avatar_items.py](app/core/avatar_items.py)의 id·slot·index는 프론트 `lib/avatar/shopItems.ts`와 반드시 같아야 합니다.
- **주석:** 코드 주석은 한국어로, 왜 그렇게 하는지 위주로 씁니다.
