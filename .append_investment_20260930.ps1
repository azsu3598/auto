[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$excel = New-Object -ComObject Excel.Application
$excel.Visible = $false
$excel.DisplayAlerts = $false
$path = "D:\Test\docs\투자 내역\투자내역_현재본.xlsx"

try {
    $wb = $excel.Workbooks.Open($path)
    $ws = $wb.Worksheets.Item("투자내역")
    $lastDataRow = $ws.Cells.Item($ws.Rows.Count, 5).End(-4162).Row
    $row = $lastDataRow + 1

    $ws.Rows.Item($row - 1).Copy()
    $ws.Rows.Item($row).PasteSpecial(-4122)

    $ws.Cells.Item($row, 1).Value2 = 46295
    $ws.Cells.Item($row, 1).NumberFormat = "yyyy-mm-dd"
    $ws.Cells.Item($row, 2).Value2 = (11 / 24 + 35 / 1440)
    $ws.Cells.Item($row, 2).NumberFormat = "hh:mm"
    $ws.Cells.Item($row, 5).Value2 = "서진시스템"
    $ws.Cells.Item($row, 6).NumberFormat = "@"
    $ws.Cells.Item($row, 6).Value2 = "178320"
    $ws.Cells.Item($row, 7).Value2 = 38750
    $ws.Cells.Item($row, 8).Value2 = 3

    $ws.Cells.Item($row, 9).Formula = ('=IF(OR(G{0}="",H{0}=""),"",G{0}*H{0})' -f $row)
    $ws.Cells.Item($row, 12).Formula = ('=IF(OR(J{0}="",K{0}=""),"",J{0}*K{0})' -f $row)
    $ws.Cells.Item($row, 14).Formula = ('=IF(OR(J{0}="",K{0}=""),"",L{0}-(G{0}*K{0})-IF(M{0}="",0,M{0}))' -f $row)
    $ws.Cells.Item($row, 15).Formula = ('=IF(OR(J{0}="",K{0}=""),"",N{0}/(G{0}*K{0}))' -f $row)
    $ws.Cells.Item($row, 15).NumberFormat = "0.00%"
    $ws.Cells.Item($row, 16).Formula = ('=IF(H{0}="","",H{0}-IF(K{0}="",0,K{0}))' -f $row)
    $ws.Cells.Item($row, 17).Formula = ('=IF(OR(A{0}="",B{0}="",C{0}="",D{0}=""),"",(C{0}+D{0})-(A{0}+B{0}))' -f $row)
    $ws.Cells.Item($row, 17).NumberFormat = "[h]:mm"

    $ws.Cells.Item($row, 18).Value2 = 38300
    $ws.Cells.Item($row, 19).Value2 = 40000
    $ws.Cells.Item($row, 20).Value2 = 40400
    $ws.Cells.Item($row, 21).Value2 = "보유"
    $ws.Cells.Item($row, 22).Value2 = "2026-09-30 11:35 사용자 실제 매수; 38,750원 3주; 총매입금액 116,250원; 기존 분석 기준 38,300원 아래 5분봉 확인 손절, 비상 37,800원; 수수료·세금 미확정"

    $wb.Save()
    Write-Output ("ADDED_ROW=" + $row)
    Write-Output ("TOTAL=" + $ws.Cells.Item($row, 9).Value2)
}
finally {
    if ($wb) { $wb.Close($true) }
    $excel.Quit()
    if ($ws) { [System.Runtime.InteropServices.Marshal]::ReleaseComObject($ws) | Out-Null }
    if ($wb) { [System.Runtime.InteropServices.Marshal]::ReleaseComObject($wb) | Out-Null }
    [System.Runtime.InteropServices.Marshal]::ReleaseComObject($excel) | Out-Null
}
