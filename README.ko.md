# academic-research-kernel

[English](README.md) · [简体中文](README.zh-Hans.md) · [繁體中文](README.zh-Hant.md) · [日本語](README.ja.md) · [한국어](README.ko.md) · [Deutsch](README.de.md) · [Français](README.fr.md) · [Español](README.es.md) · [Português](i18n/pt/README.md) · [Русский](i18n/ru/README.md) · [Bahasa Indonesia](i18n/id/README.md) · [Italiano](i18n/it/README.md) · [हिन्दी](i18n/hi/README.md) · [العربية](i18n/ar/README.md) · [বাংলা](i18n/bn/README.md) · [اردو](i18n/ur/README.md) · [Tiếng Việt](i18n/vi/README.md) · [Türkçe](i18n/tr/README.md) · [فارسی](i18n/fa/README.md) · [Kiswahili](i18n/sw/README.md) · [Polski](i18n/pl/README.md)

특정 실행 환경에 종속되지 않는 자율 에이전트 연구 워크플로용 결정론적 학술 연구 상태 관리 및 검증 도구 모음입니다. 연구 자료 수집 및 파싱 계층과 범용 Model Context Protocol(MCP) 서버를 통해 연구 객체 식별과 이력·추적성, 실증적 근거 기록 및 검증 기록, 주장과 근거의 연결, 그리고 추가 전용 연구 의사결정 및 실패 시도 기록을 하나로 통합합니다. 14개의 전문 학술 스킬이 검증된 연구 상태의 생산자이자 소비자로 작동하며, Claude Code, Cursor, Codex, Gemini CLI, Hermes Agent를 기본 지원합니다. 검증 범위와 외부 서비스 제약은 [감사 문서](docs/kernel-architecture.md)에 기록되어 있습니다.

저자: Junfu Shi (SJF, xngg1021), Hermes Agent. 현재 제공 범위: [Source Lineage License 1.0](LICENSE).

## 빠른 시작

[uv](https://docs.astral.sh/uv/getting-started/installation/)를 사용하여 버전 2.2.0을 실행합니다:

```bash
uvx academic-research-kernel@2.2.0 mcp
```

[2.2.0 릴리스](https://github.com/xngg1021/academic-research-kernel/releases/tag/v2.2.0)에는 배포 패키지 해시와 게시 상태가 기록되어 있습니다. 릴리스 wheel 파일을 내려받아 로컬에서 `uvx --from ./academic_research_kernel-2.2.0-py3-none-any.whl academic-research-kernel mcp` 명령으로 실행할 수도 있습니다. Python 3.10–3.14를 지원하며, `uvx --python 3.12`를 통해 지원되는 인터프리터를 명시적으로 선택할 수 있습니다. 통계 계산을 포함한 12개의 모든 결정론적 도구가 기본 설치에 포함되어 있습니다.

## 설치 확인

```bash
uvx academic-research-kernel@2.2.0 doctor
uvx academic-research-kernel@2.2.0 --version
```

오프라인 진단 도구는 의존성, 스키마 및 12개 도구 정의를 점검합니다. 선택적 외부 서비스는 설정하지 않아도 무방하며, 기계 판독이 가능한 출력이 필요할 때는 `doctor --json`을 사용합니다.

## 패키지 설치

```bash
uv tool install academic-research-kernel==2.2.0
academic-research-kernel doctor
academic-research-kernel mcp
```

또는 `pipx install academic-research-kernel==2.2.0`을 사용하거나, 지원되는 가상 환경 내에서 `python -m pip install academic-research-kernel==2.2.0`으로 설치할 수 있습니다. `[full]`은 확장 과학 계산 스킬 예제용 라이브러리를 추가하며, `[qa]`는 PDF 파서를 포함한 저장소 검증 도구를 추가합니다. `[research]`는 클린 설치 환경 전반에서 일관된 PDF 폰트 디코딩을 보장하기 위해 `pypdf==6.19.0`과 `fonttools==4.65.0`을 추가하며, 두 패키지 모두 Python 3.10을 지원합니다. 구조화된 HTML/XML 및 크기 제한이 있는 DOCX/XLSX 읽기는 표준 라이브러리를 사용합니다. GPU 백엔드와 유료 서비스는 선택 사항입니다.

## Hermes

Hermes 프로세스의 PATH에서 uv를 찾을 수 있도록 설치한 뒤, 이식 가능한 플러그인을 설치하고 명시적으로 활성화합니다:

```bash
hermes plugins install xngg1021/academic-research-kernel --no-enable
hermes plugins enable academic-skills
```

기존의 `academic-skills` 식별자는 그대로 유지되며 `paper-research`를 포함한 14개 스킬을 제공합니다. 플러그인의 `mcp.json`은 Python 3.12와 저장소의 `uv.lock`을 사용하여 `uv run --frozen --no-dev --no-editable`을 호출하며, 실행 환경은 `${PLUGIN_DATA}/runtime` 아래에 격리됩니다. 첫 실행 시 Hermes나 시스템 Python 패키지를 빌리지 않고 의존성을 자체 구성하므로, 누락된 패키지나 인터프리터를 내려받기 위해 네트워크 연결이 필요합니다. 기존의 스킬 전용 tap 설치 방식도 아래의 통합 안내에 따라 계속 지원됩니다.

## 소스에서 실행

```bash
git clone https://github.com/xngg1021/academic-research-kernel.git
cd academic-research-kernel
uv sync --frozen --no-dev --no-editable
uv run --frozen --no-dev --no-editable academic-research-kernel doctor
uv run --frozen --no-dev --no-editable python scripts/mcp_server.py
```

의존성 분류, 재현 절차, 릴리스 신원, 게시 점검 지점 및 검증 범위에 대한 자세한 내용은 [배포 및 릴리스 안내](docs/distribution-release.md)를 참조하십시오.

## 라이선스

본 통지를 포함한 스냅샷은 [LICENSE-APPLICATION.md](LICENSE-APPLICATION.md)에서 식별된 대상 자료와 권리에 **Source Lineage License 1.0**을 적용한다. 최초 SLL 커밋과 트리, 그리고 이후의 경계 기록 커밋은 [LICENSE-HISTORY.md](LICENSE-HISTORY.md)와 [SOURCE-LINEAGE.md](SOURCE-LINEAGE.md)에서 구분된다. 기록된 전환 시점 이후로 본 통지를 유지하는 스냅샷은 동일한 제공 범위를 지닌다.

`439ce4a29d6d2d9137308d7f9f045863e9f0c5b3`까지의 과거 스냅샷은 MIT 라이선스로 배포되었으며, 해당 복제본에 적용되는 조건을 따른다. 수령자는 유효한 MIT 권한을 보유하며 SLL로 이전할 필요가 없다. [이전 프로젝트 MIT 원문](LICENSES/MIT-pre-SLL.txt)은 보존되고, [tests/upstream/LICENSE](tests/upstream/LICENSE)와 그 서드파티 출처 기록은 변경되지 않는다. 새로운 루트 제공은 이 권한들을 지우지 않는다.

SLL은 적용 가능한 라이선스, 통지, 소스 계보 조건에 따라 사용, 연구, 수정, 상업적 이용, 배포, 독점적 추가를 폭넓게 허용한다. 카피레프트가 아니며 소스 공개를 요구하지 않는다. 복제본을 제공하지 않는 순수 네트워크 서비스는 그 자체로 핵심 서비스 계보 통지 조건을 발동하지 않는다. 명시적 특허 허여는 없다. 서드파티 자료는 각자의 조건을 따른다. 정보성 요약은 영문 원본 [LICENSE](LICENSE)가 우선한다. `LicenseRef-Source-Lineage-1.0`은 로컬 참조이며 SPDX 부여가 아니고 OSI 승인을 주장하지 않는다. [기여 수취](CONTRIBUTING.md)는 하위 라이선스 권한과 별개이다.

## 스킬

| 스킬 | 버전 | 기능 |
| --- | --- | --- |
| `skills/academic-source-verification` | 1.2.0 | 신원과 출처별 인용 수 교차 확인, 갱신·철회 신호 점검, OA 원문 위치 파악과 PDF 신원 검증 |
| `skills/literature-analysis` | 1.3.0 | 12개 워크플로: 주제 유사도, 국소 텍스트 중복, 반증, 저자 프로필, 모의 심사, 오류 점검, 리뷰 매트릭스, 저널 후보, BibTeX, 이중언어 독해, 연구 공백 선별, 재현 |
| `skills/academic-writing` | 1.1.1 | 논문 편집, 인용 규범 안내(ISO 690, APA, MLA, Chicago, IEEE, AMA 및 지역 프로필), 저널 투고 지침, 선택적 탐지 서비스, 투고 자료 및 기관 심사 요건 |
| `skills/math-computation` | 1.2.1 | 기존 영역·과제 라우팅과 수정된 수치·통계 예제, 분야별 심화 참조 문서 4편 |
| `skills/quantitative-paper-audit` | 1.1.0 | 논문이 보고한 통계량(효과 크기, p값, 신뢰구간, OR/RR, 달성 검정력) 재계산과 수치 불일치 탐지 |
| `skills/research-reproducibility` | 1.0.1 | 구조화된 점검표, 5단계 사실 계층, 재현 가능한 감사 기록을 갖춘 14단계 재현 감사 파이프라인 |
| `skills/systematic-review-meta-analysis` | 1.0.1 | PRISMA 검색 로그, 문헌 선별 기록, 효과 크기 환산, 이질성, 고정·무작위 효과 통합, 민감도와 출판 편향 진단 |
| `skills/literature-watch` | 1.1.0 | 주간 블루프린트: OpenAlex와 Crossref에서 주제·저자·DOI 인용 신규 저작을 감시하고 중복 제거 후 신규 항목만 보고 |
| `skills/retraction-watch` | 1.1.0 | 주간 블루프린트: OpenAlex `is_retracted`와 Crossref 갱신 기록(`update-to` 신호)에 대해 DOI 감시 목록을 재점검하고 상태 변화만 보고 |
| `skills/research-object-identity` | 1.1.0 | 결정론적 연구 자원 식별 및 이력·추적성: 식별자 정규화, 5가지 상태 판정, 콘텐츠 주소 지정 파생 그래프, 인과적 DAG 검증 및 100밀리초 미만의 오프라인 역방향 추적 |
| `skills/claim-evidence-graph` | 1.0.0 | 결정론적 주장과 근거의 연결: 과학적 주장, 근거 기록, 계산 이력 연결 |
| `skills/decision-ledger` | 1.0.0 | 연구 의사결정 및 실패 시도 기록: 연구 선택, 실패 시도(음성 결과), 연구 경로 상태 및 해당 경로를 중단한 이유, 결과 수정 이력을 기록하는 결정론적 추가 전용 기록부 |
| `skills/paper-research` | 1.0.0 | DOI·URL·로컬 논문 및 보충 자료 독해, 후보 필드 검증, 통계 수치 점검, 영속적 연구 상태 저장, 출처가 연결된 중국어 보고서 생성 및 두 논문 비교 |
| `skills/cross-review-five` | 2.0.0 | 임의의 모델 및 서브에이전트를 지원하는 동적 다중 검토 패널 편성(Kimi K3, DeepSeek V4 Pro, GLM 5.3, Claude, Gemini 등): Kuhn-Munkres 헝가리안 할당, 주장 수준 군집화, 표적 익명 질의 및 P0–P3 심각도 등급을 갖춘 v2 Sparse Deliberation 파이프라인 |

14개 스킬에는 총 22편의 Markdown 참조 파일이 포함되어 있으며 필요할 때만 로드됩니다.

## 학술 표준 및 다중 프로필 기준

인용 양식, 보고 지침, 메타데이터 규약은 대상 학술지, 연구지원기관, 학문 분야, 관할권에 따라 달라집니다. 본 저장소는 **ISO 690:2021**(서지 참조 및 인용 지침), **ISO 5127:2017**(정보 및 문헌 용어), **W3C PROV**(이력 및 출처 데이터 모델)를 국제 기준으로 삼고, 한국 KS X ISO 690 참조, 중국 대륙 GB/T 7714-2025, 스페인 UNE-ISO 690:2024, 독일 DIN ISO 690:2021 등 지역 프로필과 APA 7판, IEEE, ACM, Vancouver, Chicago, PRISMA 2020, ICMJE 등 학문 분야별 표준을 지원합니다. 투고 대상 기관이나 학술지의 공식 요건이 기본 프로필보다 항상 우선합니다. 자세한 내용은 [학술 표준 아키텍처](docs/standards/README.md) 및 [자연스러운 학술 용어 가이드](docs/terminology/README.md)를 참조하십시오.

버전 2.2.0은 DOI 및 외부 식별자 일관성, 상호 배타적인 정량 판정 플래그, 그리고 커널과 검증 기록이 공유하는 확인 필요 항목 규약을 검증합니다. 캐시 완전성은 보관된 원본 엔벌로프와 정규화된 바인딩으로부터 독립적으로 재구성되므로, 상태 레코드와 캐시 선언을 동시에 삭제하더라도 잘못된 캐시 재생이 승인되지 않습니다. 자세한 내용은 [4대 차단 요소 해결 기록](docs/kernel-architecture.md)을 참조하십시오.

## 통합 및 이식 가능한 사용

### 1. 범용 Agent Plugins v1 및 Model Context Protocol (MCP)
본 저장소는 벤더 중립적인 **Agent Plugins v1** 사양(`plugin.json`)을 준수하며, stdio **MCP 서버**(`mcp.json` / `scripts/mcp_server.py`)를 통해 핵심 학술 검증 및 통계 재계산 도구를 노출합니다. Claude Code, Cursor, Gemini CLI 및 모든 최신 에이전트 프레임워크와 호환됩니다(저장소 식별자는 `academic-research-kernel`이지만, 하위 호환성을 위해 플러그인 매니페스트 이름 `academic-skills`와 MCP 설정 별칭은 안정적으로 유지됩니다).

```bash
# 에이전트 환경에 stdio MCP 서버로 추가
uvx academic-research-kernel mcp
```

### 2. Hermes 고유 설치
Hermes 설치 환경에서 다음을 실행합니다:

```bash
hermes skills tap add xngg1021/academic-research-kernel
hermes skills search academic-source-verification
hermes skills install xngg1021/academic-research-kernel/skills/academic-source-verification
```

나머지 스킬은 전체 식별자의 디렉터리 이름을 바꿔 설치합니다. 일반 tap은 기본 브랜치를 읽으므로 새 tap은 위 스킬 집합을 설치합니다. 병합 전에 작업 브랜치를 검사하려면 해당 브랜치를 로컬에 체크아웃하고 설치된 Hermes 버전의 로컬 폴더 지침을 따르십시오. tap 명령이 풀 리퀘스트 브랜치를 자동으로 선택한다고 가정하지 마십시오.

번들 관련 스킬은 상류 `245e48008fa814b3251f50755eb656bd9fb86cb1` 기준으로 확인되었습니다: arxiv, grounded-citations, docx, pdf, manim-video. huggingface-hub와 llama-cpp는 선택 카탈로그에 있으며 별도 설치가 필요할 수 있습니다. ocr-and-documents와 pc-hardware-benchmark는 해당 스냅샷에 없으며 의존성도 아닙니다. 세션 도구와 문서·브라우저 백엔드는 로컬 설정에 따릅니다.

## 데이터 소스 접근

- OpenAlex 기본 쿼리는 익명으로 실행할 수 있으나 일일 예산이 작습니다. 2026-09-06 기준 문서는 익명 일일 0.10달러, 무료 API 키 일일 1달러, 초당 요청 상한 100회를 명시합니다. 비용은 쿼리 유형에 따라 다르며 무제한 접근이 아닙니다. 선택 키는 `OPENALEX_API_KEY`에 저장하고 `per_page`(최대 100)와 커서 페이지네이션을 사용하십시오.
- Crossref는 속도 제한이 있는 공개 메타데이터 접근을 제공합니다. 갱신 관계와 Retraction Watch 신호는 DOI와 방향 확인이 필요하며, 레코드 부재가 논문이 영향받지 않았다는 증명이 되지는 않습니다.
- Unpaywall은 `UNPAYWALL_EMAIL`에 실제 연락 이메일을 요구합니다. 위치가 없다고 해서 OA 사본이 없다는 증명이 되지는 않습니다.
- arXiv, Europe PMC, PubMed E-utilities, DOAJ는 각자의 정책이 있는 보조 소스이며 기본 테스트가 모두를 실행하지는 않습니다. Semantic Scholar는 공유 익명 한도와 별도 할당 키 한도가 있으며, API 접근권이 인용 맥락 가용성을 보장하지는 않습니다.
- Scite, Dimensions, Scopus, Web of Science, AI 탐지 제품은 선택적 외부 서비스입니다. 사용 전 현재 계정·API 권한과 할당량을 확인하십시오. 보편적 무료 등급이나 고정 가격은 약속되지 않습니다.

[OpenAlex 인증](https://help.openalex.org/api/authentication/), [예산과 쿼리 비용](https://help.openalex.org/api/llm-quick-reference/), [Crossref 갱신 필터](https://www.crossref.org/documentation/retrieve-metadata/rest-api/rest-api-filters/)를 참조하십시오.

## 결정론적 수집 및 공개 커널 인터페이스

버전 2.2.0은 `ResearchArtifactEnvelope v1`, `ArtifactIngestionReceipt v1`, 15개의 어댑터(14개 스킬과 opaque fallback), 그리고 12개의 무상태 stdio MCP 도구를 제공합니다. 승인된 수집 검증 기록은 보관되는 각 의미론적 변경(연구 객체, 주장과 근거의 연결 레코드, 연구 의사결정 및 실패 시도 기록 레코드, 확인 필요 항목, 물리적 검증 기록 및 산출물 등록)을 종류, 식별자, 정규 SHA-256으로 바인딩합니다. 캐시 재생은 전송 스냅샷 해시와 독립적으로 이러한 약정을 검증합니다. 빈 기록부도 유효하며, 실패한 원자적 배치는 부분 상태를 남기지 않습니다.

이력 콘텐츠 읽기 권한은 대역 외에서 명시적으로 부여됩니다. 신뢰할 수 있는 Python 호출자는 직렬화된 검증 기록이나 스냅샷을 재생할 때 `LineageVerificationContext`를 전달하며, MCP 호출자는 제한된 크기의 콘텐츠 바이트만 제공할 수 있고 호스트 파일시스템 루트는 지정할 수 없습니다. 기본 콘텐츠 예산은 10 MiB이며, 신뢰할 수 있는 호스트는 생산자와 검증자가 동일한 정책을 따르는 조건에서 더 큰 산출물을 명시적으로 허용할 수 있습니다. 콘텐츠 권한이 없으면 `fully_verified` 주장은 독립적으로 재현될 수 없으며 구조화된 무효 검증 결과를 반환합니다. 비정형 텍스트는 불투명하게 유지되고 이견은 가시적으로 보존되며, 커밋, 경로 중단, 재개, 라우팅 및 사실 판단의 통제권은 연구자에게 있습니다.

계약 및 호환성 규칙은 [커널 아키텍처 문서](docs/kernel-architecture.md)를 참조하십시오. 배포 및 게시 점검 지점은 [릴리스 가이드](docs/distribution-release.md)에 기록되어 있습니다. 영문 및 간체 중국어 README는 최신 상태로 동기화되어 있으며, 다른 번역 상태는 [다국어 매니페스트](docs/i18n/manifest.json)에 명시되어 있습니다. 최종 후보 신원, 정확한 HEAD CI, 누적 검토 및 병합 근거는 [마감 기록](https://github.com/xngg1021/academic-research-kernel/pull/12#issuecomment-5754741342)에 기록되어 있습니다.

## 검증 및 테스트

전용 Python 환경을 사용하십시오. 런타임 라이브러리는 과제별이며 Hermes에 사전 설치되어 있음을 보장하지 않습니다. QA 의존성은 표시된 모든 예제가 실행될 수 있도록 더 넓게 구성되어 있습니다:

```bash
python -m pip install -r requirements-qa.txt
python -m pip install 'torch>=2.5,<3' --index-url https://download.pytorch.org/whl/cpu
python scripts/qa.py
python -m pytest -q -rs tests
python scripts/i18n_sync.py --check
python scripts/verify_external_apis.py --output external-status.json --summary external-summary.md
git diff --check
```

QA는 메타데이터, 참조 파일, 개인 경로·알려진 시크릿 패턴, Python 구문, 표시된 실행 코드 블록을 검증합니다. 각 smoke 예제는 새 하위 프로세스에서 변경 없이 실행됩니다. 플롯 예제는 `PLOT_DIR`(기본값 `~/plots`, 명시적으로 전개)을 받으며 테스트는 임시 디렉터리를 사용합니다. 미분류 Python 코드 블록은 거부됩니다. `fragment:` 블록은 구문 검사를 거치지만 이름 있는 입력이 필요하므로 단독 실행되지 않습니다. `external-test:` 블록은 수동 외부 명령으로만 실행되며, 구성된 검사를 통과하면 0, 코드·스키마·신원 실패 시 1, 전송·인증·할당량 불가 시 2를 반환합니다. 설정되지 않은 선택적 서비스는 SKIP으로 남습니다.

고정된 Hermes 저작 테스트는 스킬별 규칙을 바꾸지 않고 재사용됩니다. 상류 전체 배포 개체군 검사는 이 tap에 적용되지 않으며, 본 저장소 테스트 하네스는 14개 스킬 전체를 검사하고 고정된 번들·선택 카탈로그에 대해 참조를 해석합니다. 이는 완전한 Hermes 설치 테스트가 아닙니다. CI는 의존성 설치에만 네트워크를 사용하며 일반 테스트는 학술 API를 호출하지 않습니다.

CI는 GitHub Actions를 통해 Linux x86_64(Python 3.10–3.14), Linux ARM64(ubuntu-24.04-arm), Ubuntu 26.04 프리뷰 Canary(ubuntu-26.04 및 ubuntu-26.04-arm), Windows x86_64, Windows ARM64(windows-11-arm), macOS ARM64(macos-latest), macOS Intel(macos-15-intel) 전 플랫폼과 아키텍처에서 전체 QA 스위트를 실행하며, 실시간 상류 Canary 검증을 포함합니다. 기준 후보 로컬 검증은 1165개 테스트를 통과했으며, 현재 수정 결과와 커버리지 경계는 [정확성 복구 기록](docs/maintenance/correctness-repair-20261008.md)에 기록되어 있습니다(원격 근거는 테스트된 HEAD를 별도로 식별합니다). 별도의 tap 통합 워크플로가 main 푸시 시 실행되어 tests/upstream/provenance.json에 기록된 고정 Hermes 체크아웃을 설치하고 본 저장소에 대해 tap add, search, install, list를 수행합니다. 정확한 버전, 검사 항목, 제약은 [감사 문서](docs/kernel-architecture.md)에 있습니다.

[tools/longtail/](tools/longtail/README.md)에는 결정론적 롱테일 요인 생성기가 포함되어 있습니다: 4096개의 SHA256 시드 후보, 30개의 선택된 시나리오 및 기계가 계산한 검증 적용 범위 보고서를 제공합니다. v3 모델은 역량군(E01), 실제 저장소의 14개 스킬(E02), 과제 목표(E03)를 별도로 집계합니다. 각 시나리오는 하나의 주요 스킬, 지원되는 과제 목표 및 호환 역량을 가지며, 모든 스킬은 선언된 핵심 목표를 포함해 최소 두 개의 서로 다른 목표 아래에서 두 번 이상 등장해야 합니다. 스킬 디렉터리 불일치는 검증 실패로 처리됩니다. 의미론적 확장(과제 체인, 오라클 및 실행 이벤트 주입)은 별도 단계로 유지되며, 요인 커버리지가 워크플로 실행 커버리지를 증명하지는 않습니다.

scripts/scfabric/은 과학 계산 및 통계 분석 도구군의 실행 계층입니다: 하드웨어 프로브, dtype 게이트가 있는 백엔드 카탈로그, 5개 워크로드 프로필, 동등성 검증이 포함된 쌍대 벤치마크 및 ComputeReceipt를 제공합니다. 이 기기에서의 1차 측정값은 [docs/scientific-compute-fabric.md](docs/scientific-compute-fabric.md)에 기록되어 있으며, 기본 원칙은 CPU를 기본으로 사용하고 검증 기록이 있을 때만 가속기를 사용하는 것입니다.

## 로컬 Agent로 논문 연구하기

`academic-research-kernel[research]==2.2.0`을 설치하고 패키지에 포함된 워크플로를 내보냅니다:

```sh
academic-research-kernel research skill --output ./agent-skills/paper-research
```

Work 또는 호환 가능한 로컬 Agent가 내보낸 `SKILL.md`를 읽게 한 다음, DOI, 공개 링크 또는 로컬 자료 번들만 제공하고 다음과 같이 요청합니다:
“研究这篇论文及其补充材料，整理方法，核对能重算的关键数字，给我一份带出处的中文报告。”
두 논문을 비교할 때는 데이터, 방법론, 평가 조건 및 결과를 비교하고 무엇이 직접 비교 가능한지 설명하도록 요청합니다. Agent는 동일한 작업 내에서 원문 읽기, 후보 필드 검증, 통계 계산, 데이터 수집, 보고서 생성 및 독립적인 원문 검토까지 이어서 수행합니다. 기존 MCP 인터페이스는 12개 도구를 그대로 유지하며, 새로운 오케스트레이션은 CLI와 이식 가능한 스킬에 자리잡고 있습니다.

실제 프로그램 실행 단계는 다음과 같습니다:

```sh
academic-research-kernel research prepare INPUT --project PROJECT
academic-research-kernel research finish --project PROJECT --candidate CANDIDATE.json
academic-research-kernel research compare LEFT_PROJECT RIGHT_PROJECT --analysis COMPARISON.json --output OUTPUT
```

`prepare`는 본문과 보충 자료를 입수·파싱하여 매니페스트, 원본 해시 및 위치가 파악된 세그먼트로 저장합니다. `finish`는 Agent가 생성한 추출 후보를 검증하고 기존 통계 도구를 사용하여 적격한 t/p값, 두 집단 효과 크기 및 빈도/백분율 주장을 재계산한 뒤 커널 상태와 중국어 Markdown/HTML 보고서를 저장합니다. `compare`는 비교 가능 조건에 대한 Agent의 명시적 평가를 검증합니다. 이 명령들은 상주 Work 모델을 내장하지 않으며, 의미론적 독해는 현재 Agent가 [paper-research](skills/paper-research/SKILL.md)를 따라 수행합니다. 저장된 원본 파일과 추출 스냅샷은 결정론적 오프라인 재생을 지원하며, 네트워크 입수와 새로운 의미론적 독해는 별도로 식별되는 작업으로 구분됩니다.

## 2.0.1 정확성 검증 및 배포 패키지 검증

제품 릴리스 2.0.1부터 적용된 정확성 보강을 통해, 공개 `academic_recompute_statistics` 도구는 t-검정 p값과 두 집단 Cohen's d / Hedges' g를 노출하며 신뢰구간(CI)과 OR/RR은 하위 수준 Python 함수로 유지됩니다. 보고된 정밀도가 중요할 때는 `p_value_literal`(예: `"1.0e-5"`) 또는 `p_value_decimals`를 전달하십시오. 리터럴은 끝자리 0을 보존하며, 수치 입력은 수치 표현만 유지합니다. 정밀도 출처가 충돌하면 명시적으로 실패합니다. 반올림(round-half-up) 비교는 하한 경계를 포함하고 상한 경계를 제외합니다. 일반적인 수치 불일치는 정상적인 과학적 검증 결과이며, 잘못된 입력이나 부분적으로 실패한 계산만 `isError`를 설정합니다.

철회 점검은 현재의 True/False/unknown 관측값을 기존에 알려진 값(last-known)과 별도로 기록합니다. 짧은 사전 쿼리 예약으로 동일 DOI 관측 순서를 정렬하고 다른 DOI의 업데이트를 보존합니다. 현재 관측값과 과거 확인 이력은 별도의 버전을 가지므로, 늦게 도착한 확인이 보관된 이력을 개선하더라도 더 최신의 unknown 관측은 현재 점검에서 미검증 상태로 명확히 유지됩니다. 회귀 체인의 HTTP 픽스처는 테스트 데이터로 표시됩니다.

MCP 서버는 `ping`에 응답하고, `notifications/cancelled`를 포함한 유효한 알림에는 침묵을 유지하며, 잘못된 입력 이후에도 stdio 세션을 유지합니다. 동기식 구현이므로 선점형 취소를 광고하지 않습니다. 메시지 처리는 [MCP 메시지 규약](https://modelcontextprotocol.io/specification/2024-11-05/basic/messages) 및 [ping 사양](https://modelcontextprotocol.io/specification/2024-11-05/basic/utilities/ping)을 따릅니다.

격리된 환경에서 현재 체크아웃의 배포 패키지를 빌드하고 검증하려면 다음을 실행합니다:

```bash
python -m build
python -m twine check --strict dist/*
python scripts/package_acceptance.py --dist dist --uvx --source-checks --report package-acceptance.json
```

`--source-checks`는 후보 sdist를 체크아웃 외부에 변경 없이 압축 해제하고, `ARK_REPO`와 `ARK_SDIST`를 해당 후보로 설정한 뒤 테스트, 정적 QA, 실행 코드 블록 및 i18n 검사를 실행합니다. wheel과 sdist 설치는 각각 새로운 환경을 사용하며, uvx는 독립된 캐시와 함께 로컬 wheel을 사용합니다. 보고서에는 산출물 해시와 설치된 임포트 경로가 기록됩니다. 정기 실행되는 경량 고정/최신 Hermes 점검은 테스트된 SHA를 독립적으로 보고합니다. 외부 계약 JSON과 작업 요약은 `healthy`, `degraded`, `failed`를 사용하며 건너뛴 프로브도 명시적으로 남깁니다.
