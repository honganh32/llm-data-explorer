$raw = [Console]::In.ReadToEnd()
try {
    $j = $raw | ConvertFrom-Json
    $msg = [System.Security.SecurityElement]::Escape([string]$j.message)
} catch {
    $msg = "Permission needed"
}
if (-not $msg) { $msg = "Permission needed" }

[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType=WindowsRuntime] | Out-Null
[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType=WindowsRuntime] | Out-Null
$xd = New-Object Windows.Data.Xml.Dom.XmlDocument
$xd.LoadXml("<toast><visual><binding template='ToastText02'><text id='1'>Claude Code</text><text id='2'>$msg</text></binding></visual></toast>")
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("Claude Code").Show((New-Object Windows.UI.Notifications.ToastNotification($xd)))
