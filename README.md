# Automotive Security Testing Lab

자동차 CAN 통신과 보안 테스트를 익히기 위해 진행한 개인 실습입니다. 가상 CAN에서 프레임을 읽는 것부터 공개 데이터 비교와 Python 의존성 검사까지 진행했습니다.

## 완료한 실습

| Lab | 무엇을 실습했나 | 확인한 결과 |
|---|---|---|
| [Lab 01 — CAN 프레임 읽기](labs/01-can-network-analysis/README.md) | 가상 CAN에서 프레임을 주고받고 Wireshark로 캡처했습니다. | PCAP에 저장된 프레임 3개의 CAN ID, 데이터 길이, Payload를 확인했습니다. |
| [Lab 02 — 소프트웨어 가상 ECU](labs/02-virtual-ecu/README.md) | Python으로 읽기·쓰기 요청을 처리하는 가상 ECU를 만들고 응답과 입력 검증을 확인했습니다. | 최종 실행에서 21개 케이스의 검사 84개가 모두 통과했습니다. |
| [Lab 03 — GEM-CAN 데이터 분석](labs/03-gem-can-analysis/README.md) | 공개 로그의 CAN ID 분포와 정상·DoS 구간의 메시지 간격을 비교했습니다. | 정상 주행 100,000행과 공격 세션 43,444행을 분석했습니다. |
| [Lab 04 — AutoHack 표본 비교와 가상 ECU 검사](labs/04-autohack-analysis/README.md) | AutoHack의 정상·퍼징 표본을 비교하고, 가상 ECU의 입력 처리는 별도로 검사했습니다. | 표본 10,000행씩에서 고유 CAN ID는 정상 108개, 퍼징 2,033개였습니다. 가상 CAN 검사 8개와 메모리 기반 회귀 검사 381개가 각각 통과했습니다. |
| [Lab 05 — Python 의존성 검사](labs/05-python-sca/README.md) | Lab 02 가상환경의 설치 패키지를 Syft로 SBOM에 기록하고 Grype로 검사했습니다. | 설치 패키지 5개를 확인했고 최종 검사에서 `pip 24.0`에 취약점 매치 6건이 나왔습니다. |
