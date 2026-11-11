# Automotive Security Testing Lab

자동차 CAN 통신과 보안 테스트를 학습하고 실습 과정과 결과를 정리하는 개인 학습 프로젝트입니다. 가상 CAN 송수신, 소프트웨어 가상 ECU 테스트, 공개 CAN 데이터셋 분석을 진행했습니다.

## 완료한 실습

| Lab | 내용 | 상태 |
|---|---|---|
| [Lab 01 — CAN Network Analysis](labs/01-can-network-analysis/README.md) | SocketCAN·vcan 송수신, Wireshark 프레임 분석 | 완료 |
| [Lab 02 — Virtual ECU](labs/02-virtual-ecu/README.md) | Python 가상 ECU 읽기·쓰기 및 입력 검증 | 완료 |
| [Lab 03 — GEM-CAN Analysis](labs/03-gem-can-analysis/README.md) | 공개 데이터셋 구조·분포 확인, 정상·DoS 트래픽 비교 | 완료 |

Lab 01은 CAN ID·데이터 길이·Payload를 캡처에서 확인했습니다. Lab 02는 최종 실행에서 21개 케이스·84개 검사 PASS, 실패 0을 기록했습니다. Lab 03은 정상 주행 100,000행과 공격 세션 43,444행을 분석하고 그래프와 DoS 상세 분석을 정리했습니다.

## 실행 방법과 결과

각 Lab README에 환경 구성, 실행 방법, 분석 결과와 원본 증적 링크를 정리했습니다.

- Lab 01·02: Linux, SocketCAN/vcan, can-utils, Wireshark, Python/python-can
- Lab 03: Python, Matplotlib, NumPy를 이용한 오프라인 데이터 분석

코드·캡처·로그·그래프는 각 `labs/` 폴더에 있습니다. Lab 03의 데이터셋 출처와 다운로드 방법은 해당 README에서 확인할 수 있습니다.
