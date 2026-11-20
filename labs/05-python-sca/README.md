# Lab 05. Python SCA·SBOM·CVE 검사

Lab 02의 Python 가상환경을 대상으로 소프트웨어 구성 분석(SCA)을 실습했다. 설치 패키지를 확인하고 Syft로 CycloneDX SBOM을 생성한 뒤 Grype로 알려진 취약점과 대조했다.

- 환경 및 도구 — Python 3.12 가상환경, pip 24.0, Syft 1.57.2, Grype 0.122.1
- 검사 범위 — `labs/02-virtual-ecu/.venv/lib/python3.12/site-packages`

## 설치 패키지와 SBOM

가상환경의 `pip freeze --all`, [저장된 설치 목록](evidence/20261120-054107/pip-list.txt), 두 SBOM의 PyPI 패키지 이름과 버전이 일치했다. `typing_extensions`는 SBOM에서 `typing-extensions`로 표기됐다.

| 패키지 | 버전 |
| --- | --- |
| `packaging` | `26.3` |
| `pip` | `24.0` |
| `python-can` | `4.6.1` |
| `typing_extensions` | `4.16.0` |
| `wrapt` | `1.17.3` |

두 CycloneDX SBOM의 최상위 `components`는 각각 **1,280개**다. `library` 5개가 설치 패키지이며, `file` 1,275개는 소스·메타데이터·바이트코드 등의 파일 항목이다.

## Grype 결과

| 검사 시각 (2026-11-20 KST) | SBOM | Grype 결과 | Medium | Low | 합계 |
| --- | --- | --- | ---: | ---: | ---: |
| 기존 14:44:59 | [sbom.cdx.json](evidence/public/20261120-054107/sbom.cdx.json) | [grype.json](evidence/public/20261120-054107/grype.json) | 5 | 1 | 6 |
| 최종 14:53:45 | [sbom-python.cdx.json](evidence/public/20261120-054107/sbom-python.cdx.json) | [grype-final.json](evidence/public/20261120-054107/grype-final.json) | 5 | 1 | 6 |

두 검사 모두 같은 DB 빌드(`2026-11-19T18:41:05Z`)를 사용했고, `pip 24.0`에서 동일한 GHSA 6건이 탐지됐다. 아래 CVE는 각 GHSA에 연결된 식별자다.

- Medium — `CVE-2025-8869`, `CVE-2026-8643`, `CVE-2026-13346`, `CVE-2026-6357`, `CVE-2026-3219`
- Low — `CVE-2026-1703`

최종 검사에서 다른 네 패키지에 대한 매치는 없었다. 결과는 해당 DB 스냅샷과 패키지 버전의 매칭을 보여준다. 실행 환경에서 각 취약점의 영향 여부는 확인하지 않았다.

## 재현 명령

저장소 루트에서 일반 사용자 권한으로 실행한다. 위 가상환경과 Syft·Grype가 필요하며, Grype DB가 로컬에 없으면 다운로드 환경이 필요하다. 명령은 재현용이며 새 검사는 실행하지 않았다.

```bash
venv=labs/02-virtual-ecu/.venv
out=$(mktemp -d labs/05-python-sca/evidence/repro-XXXXXXXX)
PYTHONDONTWRITEBYTECODE=1 "$venv/bin/python" -m pip freeze --all > "$out/pip-list.txt"
syft scan "dir:$venv/lib/python3.12/site-packages" -o cyclonedx-json > "$out/sbom.cdx.json"
grype "sbom:$out/sbom.cdx.json" -o json > "$out/grype.json"
```

새 결과 디렉터리에 설치 목록, SBOM, 검사 JSON이 생성된다. 가상환경의 설치 상태와 Grype DB 버전에 따라 재실행 결과가 달라질 수 있다. 표에 링크한 공개용 JSON은 원본의 로컬 절대 경로만 치환한 사본이다. 원본 JSON, 가상환경, 캐시, 재실행 결과는 Git에서 제외한다.
