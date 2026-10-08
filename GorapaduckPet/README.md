# 디지몬 데스크톱 펫

디지타마부터 시작해 여러 갈래로 진화하는 Windows 바탕화면 육성 펫입니다.
디지몬 정보와 이미지, 진화 관계는 실행 중 Digi-API에서 가져옵니다.

한 번에 최대 6마리를 키울 수 있으며 각 펫의 성장, 유대감, 진화 이력,
크기와 화면 위치는 서로 독립적으로 저장됩니다. 기존 단일 펫 저장 파일은
처음 실행할 때 다중 펫 로스터 형식으로 자동 변환됩니다.

## 실행

Visual Studio 2022 또는 .NET 8 SDK가 설치된 Windows 터미널에서:

```powershell
dotnet run --project GorapaduckPet.csproj
```

실행 파일 만들기:

```powershell
dotnet publish GorapaduckPet.csproj -c Release -r win-x64 --self-contained false -p:PublishSingleFile=true
```

결과는 `bin\Release\net8.0-windows\win-x64\publish\DigiDesktopPet.exe`에 생성됩니다.

## 조작

- 왼쪽 드래그: 위치 이동
- 두 번 클릭: 쓰다듬기
- 마우스 휠: 크기 조절
- 오른쪽 클릭: 밥, 놀이, 수면, 일시정지, 설정, 종료
- 트레이 아이콘 두 번 클릭: 펫 보이기/숨기기

펫 크기를 바꿔도 말풍선과 상태 안내창은 축소되지 않습니다. 말풍선 위치는
현재 알 또는 디지몬 크기에 맞춰 머리 바로 위로 이동합니다.
펫 크기는 20%부터 135%까지 조절할 수 있습니다.

디지타마는 성장도 30에 Botamon으로 부화합니다. 이후 성장도 100마다 Digi-API의
다음 진화 후보 중 유대감, 기분, 돌봄 실수에 맞는 가지로 진화합니다.
API 응답이 느리거나 실패하면 기존 모습은 그대로 유지되며, 고정 크기 오류 안내와
우클릭 메뉴의 `디지몬 데이터 다시 불러오기`가 표시됩니다.

설정과 상태는 `%LOCALAPPDATA%\DigiDesktopPet\settings.json`에 저장됩니다.

Digimon 관련 명칭과 이미지의 권리는 각 권리자에게 있습니다. 공개 배포나 판매 전에는
별도의 사용 권한을 확인하세요. 데이터 출처: https://digi-api.com/
