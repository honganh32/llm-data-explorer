[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType=WindowsRuntime] | Out-Null
[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType=WindowsRuntime] | Out-Null
$xd = New-Object Windows.Data.Xml.Dom.XmlDocument
$xd.LoadXml('<toast><visual><binding template="ToastText01"><text id="1">Claude Code finished</text></binding></visual></toast>')
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("Claude Code").Show((New-Object Windows.UI.Notifications.ToastNotification($xd)))
