# 글로벌 AGENTS 규칙 공유본

작성: 2026-10-15 / PC-D.
원본: `/home/seunghyeon/.codex/AGENTS.md`를 읽어 이 문서의 원문 블록으로 옮겼다.
공유본은 원본의 자동 동기화본이 아니다. 원본 수정 시 내용을 비교하고 갱신해야 한다.
PC-C 전역 설정은 이번에 조회하지 않았으므로 두 PC의 규칙이 같다고 단정하지 않는다.

## 적용 시 주의

- Claude에게 전역 규칙까지 전달하기 위한 저장소 내부 공유본이다.
- 실제 전역 원본에 접근할 수 있으면 비교하고, 없으면 이 공유본을 사용한다.
- 전역 설정이나 권한을 바꾸지 않았고 원본 파일도 수정하지 않았다.
- **이 프로젝트의 Markdown은 외부 기본 폴더가 아니라 현재 저장소 내부에 작성한다.**
  프로젝트 `AGENTS.md`의 명시적 예외가 아래 전역 기본값보다 우선한다.
- 사용자에게 Windows 드라이브의 파일을 안내할 때는 `C:/...`, `D:/...` 형식으로 변환한다.
  PC-C와 PC-D는 실제 경로가 다르므로 경로를 그대로 복사해 실행하지 않는다.
- 아래 `smart-talk` 규칙은 해당 프로젝트에 대한 전역 지시다. 현재 주식 프로젝트를
  `smart-talk`으로 취급하거나 그 폴더를 새로 만들라는 뜻이 아니다.
- 원문에 나오는 WSL 경로는 원본 보존용이며 현재 프로젝트의 문서 저장 위치가 아니다.

## 원문 스냅샷

```markdown
# Global Codex guidance

- When writing markdown files, create them under `/mnt/d/Dev/2026/SKR/docs` by default.
- Do not place new markdown docs inside the `smart-talk` project folder unless the user explicitly asks for that repo-local location.

# Windows VS Code path rules

VS Code is running on Windows.
Codex is running inside WSL.

For user-visible file references:

- Convert WSL-mounted Windows paths to Windows paths.
- `/mnt/c/...` -> `C:/...`
- `/mnt/d/...` -> `D:/...`
- `/mnt/e/...` -> `E:/...`
- Preserve line numbers.
- Use Windows paths when referring to files that are located under `/mnt/<drive>/`.
- Do not show `/mnt/<drive>/...` paths when a Windows equivalent exists.

Examples:

`/mnt/d/Dev/2026/SKR/smart-talk/src/App.vue:120`
-> `D:/Dev/2026/SKR/smart-talk/src/App.vue:120`
```

다른 인증·설정·세션 파일은 이 공유본에 포함하지 않았다.
