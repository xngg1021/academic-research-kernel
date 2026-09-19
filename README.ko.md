# academic-research-kernel

[English](README.md) · [简体中文](README.zh-Hans.md) · [繁體中文](README.zh-Hant.md) · [日本語](README.ja.md) · [한국어](README.ko.md) · [Deutsch](README.de.md) · [Français](README.fr.md) · [Español](README.es.md) · [Português](i18n/pt/README.md) · [Русский](i18n/ru/README.md) · [Bahasa Indonesia](i18n/id/README.md) · [Italiano](i18n/it/README.md) · [हिन्दी](i18n/hi/README.md) · [العربية](i18n/ar/README.md) · [বাংলা](i18n/bn/README.md) · [اردو](i18n/ur/README.md) · [Tiếng Việt](i18n/vi/README.md) · [Türkçe](i18n/tr/README.md) · [فارسی](i18n/fa/README.md) · [Kiswahili](i18n/sw/README.md) · [Polski](i18n/pl/README.md)

하네스 중립적 학술 연구 핵심 및 다중 에이전트 심의 제품군. 휴대용 Agent Plugins v1 및 MCP 진입점과 함께 13가지 학술 스킬 및 검증 도구를 제공하며, Hermes Agent, Claude Code, Cursor 및 맞춤형 CLI 하위 에이전트를 위한 네이티브 통합을 지원합니다. 출처 검증, 문헌 분석, 학술 집필, 수치 계산, 정량 논문 감사, 재현 감사, 체계적 문헌고찰과 메타 분석, 연구 객체 식별과 계보, 교차 모델 리뷰 편성, 그리고 주간 모니터링 자동화 두 건을 다룹니다. 저장소에는 실행 가능한 예제 검사가 포함되어 있으며, 검증 범위와 외부 서비스 제약은 [감사 문서](docs/audit-20260906.md)에 기록되어 있습니다.

저자: Junfu Shi (SJF, xngg1021), Hermes Agent. 현재 제공 범위: [Source Lineage License 1.0](LICENSE).

## 라이선스

본 통지를 포함한 스냅샷은 [LICENSE-APPLICATION.md](LICENSE-APPLICATION.md)에서 식별된 대상 자료와 권리에 **Source Lineage License 1.0**을 적용한다. 최초 SLL 커밋과 트리, 그리고 이후의 경계 기록 커밋은 [LICENSE-HISTORY.md](LICENSE-HISTORY.md)와 [SOURCE-LINEAGE.md](SOURCE-LINEAGE.md)에서 구분된다. 기록된 전환 시점 이후로 본 통지를 유지하는 스냅샷은 동일한 제공 범위를 지닌다.

`439ce4a29d6d2d9137308d7f9f045863e9f0c5b3`까지의 과거 스냅샷은 MIT 라이선스로 배포되었으며, 해당 복제본에 적용되는 조건을 따른다. 수령자는 유효한 MIT 권한을 보유하며 SLL로 이전할 필요가 없다. [이전 프로젝트 MIT 원문](LICENSES/MIT-pre-SLL.txt)은 보존되고, [tests/upstream/LICENSE](tests/upstream/LICENSE)와 그 서드파티 출처 기록은 변경되지 않는다. 새로운 루트 제공은 이 권한들을 지우지 않는다.

SLL은 적용 가능한 라이선스, 통지, 소스 계보 조건에 따라 사용, 연구, 수정, 상업적 이용, 배포, 독점적 추가를 폭넓게 허용한다. 카피레프트가 아니며 소스 공개를 요구하지 않는다. 복제본을 제공하지 않는 순수 네트워크 서비스는 그 자체로 핵심 서비스 계보 통지 조건을 발동하지 않는다. 명시적 특허 허여는 없다. 서드파티 자료는 각자의 조건을 따른다. 정보성 요약은 영문 원본 [LICENSE](LICENSE)가 우선한다. `LicenseRef-Source-Lineage-1.0`은 로컬 참조이며 SPDX 부여가 아니고 OSI 승인을 주장하지 않는다. [기여 수취](CONTRIBUTING.md)는 하위 라이선스 권한과 별개이다.

## 스킬

| 스킬 | 버전 | 기능 |
| --- | --- | --- |
| `skills/academic-source-verification` | 1.2.0 | 신원과 출처별 인용 수 교차 확인, 갱신·철회 신호 점검, OA 원문 위치 파악과 PDF 신원 검증 |
| `skills/literature-analysis` | 1.3.0 | 12개 워크플로: 주제 유사도, 국소 텍스트 중복, 반증, 저자 프로필, 모의 심사, 오류 점검, 리뷰 매트릭스, 저널 후보, BibTeX, 이중언어 독해, 연구 공백 선별, 재현 |
| `skills/academic-writing` | 1.1.1 | 논문 보조 편집, 인용 규범 안내(ISO 690 국제 기준 및 지역·기관 프로필), 저널 투고 지침, 선택적 탐지 서비스, 투고 자료 및 심사 요건 |
| `skills/math-computation` | 1.2.1 | 기존 영역·과제 라우팅과 수정된 수치·통계 예제, 분야별 참조 문서 4편 |
| `skills/quantitative-paper-audit` | 1.1.0 | 논문이 보고한 통계량(효과 크기, p값, 신뢰구간, OR/RR, 달성 검정력) 재계산과 수치 불일치 탐지 |
| `skills/research-reproducibility` | 1.0.1 | 구조화된 점검표, 5단계 사실, 재현 가능한 감사 기록을 갖춘 14단계 재현 감사 파이프라인 |
| `skills/systematic-review-meta-analysis` | 1.0.1 | PRISMA 검색 로그, 문헌 선별 기록, 효과 크기 환산, 이질성, 고정·무작위 효과 통합, 민감도와 출판 편향 진단 |
| `skills/literature-watch` | 1.1.0 | 주간 블루프린트: OpenAlex와 Crossref에서 주제·저자·DOI의 신규 저작을 감시하고 중복 제거 후 신규 항목만 보고 |
| `skills/retraction-watch` | 1.1.0 | 주간 블루프린트: OpenAlex is_retracted와 Crossref 갱신 기록(update-to 신호)에 대해 DOI 감시 목록을 재점검하고 상태 변화만 보고 |
| `skills/research-object-identity` | 1.1.0 | 결정론적 연구 자원 식별 및 이력·추적성: 식별자 정규화, 5가지 상태 판정, 콘텐츠 주소 지정 파생 그래프, 인과적 DAG 검증 및 밀리초 단위 오프라인 역방향 추적 |
| `skills/claim-evidence-graph` | 1.0.0 | 결정론적 주장과 근거의 연결: 과학적 주장, 실증 근거 기록, 계산 이력 연결 |
| `skills/decision-ledger` | 1.0.0 | 연구 의사결정 및 실패 시도 기록: 연구 선택, 실패 시도, 경로 중단 사유, 결과 수정 이력을 기록하는 결정론적 추가 전용 기록부 |
| `skills/cross-review-five` | 2.0.0 | 임의의 모델 및 서브에이전트를 지원하는 동적 다중 검토 패널 (Kimi K3, DeepSeek V4 Pro, GLM 5.3, Claude, Gemini 등): v2 4단계 Sparse Deliberation 파이프라인 (헝가리안 알고리즘 기반 상호보완적 블라인드 질의, P0-P3 심각도 지원) |

13개 스킬에는 21편의 Markdown 참조 파일이 있으며 필요할 때만 로드된다.

## 학술 표준 및 다중 프로필 기준

인용 양식, 보고 지침, 메타데이터 규약은 대상 학술지, 연구지원기관, 학문 분야, 관할권에 따라 달라집니다. 본 저장소는 **ISO 690:2021**(서지 참조 및 인용 지침), **ISO 5127:2017**(정보 및 문헌 용어), **W3C PROV**(이력 및 출처 데이터 모델)를 국제 기준으로 삼고, 한국 KS X ISO690 참조, 중국 대륙 GB/T 7714-2025, 스페인 UNE-ISO 690:2024 등 지역 프로필과 APA, IEEE, PRISMA 2020, ICMJE 등 학문 분야별 표준을 지원합니다. 투고 대상 기관이나 학술지의 공식 요건이 항상 최우선합니다. 자세한 내용은 [학술 표준 아키텍처](docs/standards/README.md) 및 [자연스러운 학술 용어 가이드](docs/terminology/README.md)를 참조하십시오.

## 통합 및 이식 가능한 사용 (Integration & Portable Usage)

### 1. 범용 Agent Plugins v1 및 Model Context Protocol (MCP)
본 저장소는 벤더 중립적인 **Agent Plugins v1** 사양(`plugin.json`)을 준수하며, stdio **MCP 서버**(`mcp.json` / `python scripts/mcp_server.py`)를 통해 핵심 학술 검증 및 통계 재계산 도구를 노출합니다. Claude Code, Cursor, Gemini CLI 및 모든 최신 에이전트 프레임워크와 호환됩니다.

```bash
# 에이전트 하네스에 stdio MCP 서버로 추가
python scripts/mcp_server.py
```

### 2. Hermes 고유 설치
Hermes 설치 환경에서:

```bash
hermes skills tap add xngg1021/academic-research-kernel
hermes skills search academic-source-verification
hermes skills install xngg1021/academic-research-kernel/skills/academic-source-verification
```

나머지 스킬은 전체 식별자의 디렉터리 이름을 바꿔 설치한다. 일반 tap은 기본 브랜치를 읽으므로 새 tap은 위 스킬 집합을 설치한다. 병합 전에 작업 브랜치를 검사하려면 해당 브랜치를 로컬에 체크아웃하고 설치된 Hermes 버전의 로컬 폴더 지침을 따른다. tap 명령이 PR 브랜치를 선택한다고 가정하지 말 것.

번들 관련 스킬은 상류 `245e48008fa814b3251f50755eb656bd9fb86cb1` 기준으로 확인되었다: arxiv, grounded-citations, docx, pdf, manim-video. huggingface-hub와 llama-cpp는 선택 카탈로그에 있으며 별도 설치가 필요할 수 있다. ocr-and-documents와 pc-hardware-benchmark는 해당 스냅샷에 없으며 의존성도 아니다. 세션 도구와 문서·브라우저 백엔드는 로컬 설정에 따른다.

## 데이터 소스 접근

- OpenAlex 기본 쿼리는 익명으로 실행할 수 있으며 일일 예산이 작다. 2026-09-06 현재 문서는 익명 일일 0.10달러, 무료 API 키 일일 1달러, 초당 요청 상한 100을 명시한다. 비용은 쿼리 유형에 따라 다르며 무제한 접근이 아니다. 선택 키는 `OPENALEX_API_KEY`에 저장한다. `per_page`(최대 100)와 커서 페이지네이션을 사용한다.
- Crossref는 스로틀링이 있는 공개 메타데이터 접근을 제공한다. 갱신 관계와 Retraction Watch 신호는 DOI와 방향 확인이 필요하며, 레코드 부재는 논문이 영향받지 않았다는 증명이 되지 않는다.
- Unpaywall은 `UNPAYWALL_EMAIL`에 실재 연락 이메일을 요구한다. 위치가 없다고 해서 OA 사본이 없다는 증명이 되지 않는다.
- arXiv, Europe PMC, PubMed E-utilities, DOAJ는 각자의 정책이 있는 보조 소스다. 기본 테스트가 모두를 실행하지는 않는다. Semantic Scholar는 공유 익명 한도와 별도 할당 키 한도가 있다. 접근권이 인용 맥락 가용성을 보장하지는 않는다.
- Scite, Dimensions, Scopus, Web of Science, AI 탐지 제품은 선택적 외부 서비스다. 사용 전 현재 계정·API 권한과 할당량을 확인한다. 보편적 무료 등급이나 고정 가격은 약속되지 않는다.

[OpenAlex 인증](https://help.openalex.org/api/authentication/), [예산과 쿼리 비용](https://help.openalex.org/api/llm-quick-reference/), [Crossref 갱신 필터](https://www.crossref.org/documentation/retrieve-metadata/rest-api/rest-api-filters/) 참조.

## 검증

전용 Python 환경을 사용한다. 런타임 라이브러리는 과제별이며 Hermes에 설치되어 있음을 보장하지 않는다. QA 의존성은 모든 표시된 예제가 실행될 수 있도록 더 넓다:

```bash
python -m pip install -r requirements-qa.txt
python -m pip install 'torch>=2.5,<3' --index-url https://download.pytorch.org/whl/cpu
python scripts/qa.py
python -m pytest -q tests
python scripts/verify_external_apis.py
git diff --check
```

QA는 메타데이터, 참조 파일, 개인 경로·알려진 시크릿 패턴, Python 구문, 표시된 실행 펜스를 검증한다. 각 smoke 예제는 새 하위 프로세스에서 변경 없이 실행된다. 플롯 예제는 `PLOT_DIR`(기본 `~/plots`, 명시적으로 전개)을 받고 테스트는 임시 디렉터리를 사용한다. 미분류 Python 펜스는 거부된다. `fragment:` 블록은 구문 검사되지만 이름 있는 입력이 필요하며 단독 실행되지 않는다. `external-test:` 블록은 수동 외부 명령으로만 실행된다. 통과한 구성 검사에는 0, 코드·스키마·신원 실패에는 1, 전송·인증·할당량 불가에는 2를 반환한다. 미구성 선택 서비스는 SKIP으로 남는다.

고정된 Hermes 저작 테스트는 스킬별 규칙을 바꾸지 않고 재사용된다. 상류 전체 배포 개체군 검사는 이 tap에 적용되지 않으며, 본 저장소 하네스는 13개 스킬 전체를 검사하고 고정된 번들·선택 카탈로그에 대해 참조를 해석한다. 이는 완전한 Hermes 설치 테스트가 아니다. CI는 의존성 설치에만 네트워크를 사용하며 일반 PR 테스트는 학술 API를 호출하지 않는다.

CI는 GitHub Actions로 Linux x86_64 (Python 3.10-3.14), Linux ARM64 (ubuntu-24.04-arm), Ubuntu 26.04 프리뷰 Canary (ubuntu-26.04 및 ubuntu-26.04-arm), Windows x86_64, Windows ARM64 (windows-11-arm), macOS ARM64 (macos-latest), macOS Intel (macos-15-intel) 전 플랫폼 및 전 아키텍처에 걸쳐 실행되며, 629개 단위 테스트 전원 통과와 최신 상류 main 실시간 Canary 검증을 포함한다. 별도의 tap 통합 워크플로가 main 푸시에서 실행되어 tests/upstream/provenance.json에 기록된 고정 Hermes 체크아웃을 설치하고 이 저장소에 대해 tap add, search, install, list를 수행한다. 정확한 버전, 검사 항목, 제약은 [감사 문서](docs/audit-20260906.md)에 있다.

tools/longtail/ 디렉터리는 결정론적 극한 롱테일 시나리오 생성기를 호스팅합니다: 분리된 요인 축 전반에 걸친 4096개의 SHA256 시드 조합, 탐욕적 커버리지 선택, 그리고 generated-scenarios.json 내의 기계 계산 커버리지 보고서를 제공합니다. 이는 스킬 스트레스 테스트의 입력 레이어입니다.

scripts/scfabric/ 디렉터리는 과학 계산 및 통계 분석 실행 계층입니다: 하드웨어 프로브, dtype 게이트 백엔드 카탈로그, 5개 워크로드 프로필, 동등성 검증 벤치마크 및 ComputeReceipt를 포함합니다. 측정값은 [docs/scientific-compute-fabric.md](docs/scientific-compute-fabric.md)를 참조하십시오.

## 연구·계획 문서

- [고통 지도 v0(영어)](docs/pain-atlas-v0.en.md), [中文版](docs/pain-atlas-v0.zh.md): 학술 지식 작업 생애주기의 마찰점. 정량 주장에는 출처 검증 상태를 붙인다.
- [연구 계획 v0(영어)](docs/research-plan-v0.en.md), [中文版](docs/research-plan-v0.zh.md): Research Object 모델, 핵심 역량 영역, 후보 방향, 1단계 요인 분해 행렬.
