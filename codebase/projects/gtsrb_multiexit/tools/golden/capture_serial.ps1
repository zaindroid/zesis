param(
    [string]$Port = "COM3",
    [int]$Baud = 115200,
    [int]$TimeoutSec = 60,
    [string]$OutFile = "board_capture.txt",
    [string]$ReadyFile = ""
)

$sp = New-Object System.IO.Ports.SerialPort $Port, $Baud, ([System.IO.Ports.Parity]::None), 8, ([System.IO.Ports.StopBits]::One)
$sp.DtrEnable = $false
$sp.RtsEnable = $false
$sp.ReadTimeout = 500
$sp.Open()

# Drop whatever was already buffered before we started listening.
Start-Sleep -Milliseconds 200
$sp.DiscardInBuffer()

if ($ReadyFile -ne "") {
    Set-Content -Path $ReadyFile -Value "ready"
}

$sw = New-Object System.IO.StreamWriter $OutFile, $false
$deadline = (Get-Date).AddSeconds($TimeoutSec)
while ((Get-Date) -lt $deadline) {
    try {
        $line = $sp.ReadLine()
        $sw.WriteLine($line)
        $sw.Flush()
    } catch [System.TimeoutException] {
        continue
    }
}
$sw.Close()
$sp.Close()
