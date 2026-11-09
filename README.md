# Automotive Security Testing Lab

아우토크립트의 자동차 사이버보안 테스트 엔지니어 직무를 준비하기 위한 개인 실습 프로젝트입니다. Linux의 가상 CAN 환경에서 차량 통신 프로토콜을 학습하고, 가상 ECU 보안 테스트, 퍼징(Fuzzing), 소프트웨어 구성 분석(SCA) 및 소프트웨어 자재 명세서(SBOM) 분석으로 확장하는 것을 목표로 합니다.

현재 증적은 가상 CAN 통신과 Wireshark 기본 분석에 한정됩니다. 실제 차량 또는 물리 ECU에 대한 시험, 취약점 발견, 제품 검증을 수행한 프로젝트가 아닙니다. 특정 기업의 공식 프로젝트나 평가 결과를 의미하지 않습니다.

## 아키텍처와 실습 흐름

현재 Lab 01의 실습 구성입니다. `candump`와 Wireshark는 관찰 도구이며 ECU 역할을 하지 않습니다.

```text
Linux 사용자 공간                  Linux 커널
cansend ─── CAN_RAW / SocketCAN ──> vcan0
                                      │
candump <──────────────────────────────┤
Wireshark <────────────────────────────┘
    └─ PCAP 저장 → CAN ID / 데이터 길이 / Payload 분석
```

학습 순서는 다음과 같습니다. Lab 02 이후는 아직 구현하지 않았습니다.

```text
Lab 01: 가상 CAN 송수신 및 분석
  → Lab 02: 소프트웨어 가상 ECU 개발 [계획]
  → CAN 입력 퍼징과 동작 판정 [계획]
  → SCA / SBOM 생성 및 분석 [계획]
```

## 기술 스택

| 기술 | 용도 | 현재 상태 |
|---|---|---|
| Ubuntu 24.04 | Linux 실습 환경 | 사용자 기록 기준, 버전 출력 증적 없음 |
| SocketCAN / vcan | 가상 CAN 인터페이스 | 터미널 화면과 SocketCAN 캡처 확인 |
| can-utils (`cansend`, `candump`) | CAN 프레임 송수신 | 실행 화면 확인 |
| Wireshark | 프레임 분석 및 표시 필터(Display filter) | 스크린샷 확인 |
| PCAP | 패킷 증적 저장 | 원본 형식·내용 확인 |
| Python 등 가상 ECU 구현 도구 | 가상 ECU 및 테스트 자동화 | 도구 선정·구현 예정 |
| Fuzzing / SCA / SBOM 도구 | 입력 변이 및 의존성 분석 | 도구 선정·실습 예정 |

## Lab별 진행 상태

| Lab | 내용 | 상태 | 문서 |
|---|---|---|---|
| 01 | CAN Network Analysis | 기본 송수신·분석 증적 확보 및 문서화, 문서 절차의 재실행은 미검증 | [Lab 01](labs/01-can-network-analysis/README.md) |
| 02 | Virtual ECU | 계획 | 구현 및 문서 없음 |
| 후속 | Fuzzing | 계획 | 구현 및 문서 없음 |
| 후속 | SCA / SBOM | 계획 | 구현 및 문서 없음 |

## 저장소 구조

아래는 현재 파일만 표시한 구조입니다.

```text
.
├── README.md
├── AGENTS.md
├── .gitignore
└── labs/
    └── 01-can-network-analysis/
        ├── README.md
        ├── captures/
        │   └── lab01-can-basic-communication.pcap
        └── screenshots/
            ├── 01-can-frame-analysis.png
            ├── 02-can-id-filtering.png
            └── lab01-can-communication.png
```

Lab 02는 향후 `labs/02-virtual-ecu/` 아래에 README, `src/`, `tests/`, `captures/`, `logs/`를 두는 구조를 계획합니다. 먼저 요청·응답 CAN ID, Payload 형식, 길이 조건과 오류 처리 규칙을 정의하고, 정상 입력과 비정상 입력에 대한 기대 동작을 명시할 예정입니다. Lab 01의 프레임에 요청·응답 의미를 소급해서 부여하지 않습니다.

## 실행 및 증적

- [Lab 01 환경 구성과 재현 절차](labs/01-can-network-analysis/README.md#재현-절차)
- [원본 PCAP 다운로드](labs/01-can-network-analysis/captures/lab01-can-basic-communication.pcap)
- [CAN 프레임 분석 화면](labs/01-can-network-analysis/screenshots/01-can-frame-analysis.png)
- [CAN ID 필터 화면](labs/01-can-network-analysis/screenshots/02-can-id-filtering.png)
- [가상 CAN 송수신 터미널 화면](labs/01-can-network-analysis/screenshots/lab01-can-communication.png)

저장소 루트에서 기존 증적을 여는 명령입니다. GUI 환경과 Wireshark 설치가 필요합니다.

```bash
wireshark labs/01-can-network-analysis/captures/lab01-can-basic-communication.pcap
```

원본은 **PCAP v2.4 / SocketCAN / 마이크로초 정밀도**이며 PCAPNG가 아닙니다. 터미널 화면과 PCAP의 일부 Payload가 다르므로 동일 실행의 증적으로 단정하지 않습니다. 상세 데이터와 해석 한계는 Lab 01 문서에 기록했습니다.
