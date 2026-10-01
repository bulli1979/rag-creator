<?php
// Load environment-specific config (gitignored; copy config.php.example → config.php).
require(__DIR__ . "/config.php");

$host = gethostbyaddr($_SERVER['REMOTE_ADDR']);
if ($host === false || $host === $_SERVER['REMOTE_ADDR']) {
    die("Access denied"); // DNS failed — deny
}

$allowedHostSuffix = defined('NOTBOT_ALLOWED_HOST_SUFFIX')
  ? strtolower(trim(NOTBOT_ALLOWED_HOST_SUFFIX, '.'))
  : '';
$normalizedHost = strtolower(rtrim($host, '.'));
$isAllowedHost = $allowedHostSuffix !== '' && (
  $normalizedHost === $allowedHostSuffix
  || substr($normalizedHost, -strlen('.' . $allowedHostSuffix)) === '.' . $allowedHostSuffix
);
if (!$isAllowedHost) {
  die("Access denied");
}

#require("access_control.inc.php");
#
#if (!access_allowed(NOTBOT_ACCESS_SECTION)) {
#    echo 'Access denied';
#    exit;
#}

?>
<!DOCTYPE html PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN">
<html>
<head>
  <meta http-equiv="Content-Type" content="text/html; charset=utf-8">
  <title>NOTBot – NOT AI Assistant</title>
  <link rel="icon" href="/g/notlogo.ico" type="image/x-icon">
  <link rel="shortcut icon" href="/g/notlogo.ico" type="image/x-icon">
  <script type="text/javascript" src="/include/styleSwitch.js"><!-- function setStyle() {void(0);} //--></script>
  <link rel="stylesheet" type="text/css" href="/include/styleGen.css">
  <link rel="stylesheet" type="text/css" href="/include/styleFontMed.css">
  <link rel="alternate stylesheet" type="text/css" media="screen" title="smallfont" href="/include/styleFontSmall.css">
  <link rel="alternate stylesheet" type="text/css" media="screen" title="bigfont"   href="/include/styleFontBig.css">
  <script type="text/javascript" src="/include/coolmenu.js"></script>
  <?php if ($isAllowedHost): ?>
    <script type="text/javascript" src="/include/menuitems.js"></script>
  <?php else: ?>
    <script type="text/javascript" src="/include/menuitems_pub.js"></script>
  <?php endif; ?>
  <!-- NOTBot chat UI fonts and styles -->
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500;9..144,700&family=Space+Grotesk:wght@400;500;700&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="./styles.css">
</head>

<body marginheight="0" marginwidth="0" topmargin="0" leftmargin="0"
      bgcolor="#ffffff" link="#0000ff" vlink="#0000ff" alink="#ff0000" onload="setStyle();">

<script type="text/javascript">new COOLjsMenu("menu1", MENU_ITEMS)</script>

<a name="Top"></a>

<table width="100%" border="0" cellspacing="0" cellpadding="0" height="100%">
<tr>

<td bgcolor="#0080ff" valign="top" align="center">
  <img src="/g/notlogo3_100pix.png" width="100" height="100" vspace="10" hspace="0" alt=""><br>
  <img src="/g/trans-box.gif" width="120" height="1" alt="">
  <img src="/g/trans-box.gif" width="1" height="225" alt=""><br>
  <a href="/general/searchform.html"><img src="/g/search_icon.gif" alt="Search" width="110" height="30" border="0"></a><br>
  <img src="/g/label_textsize.gif" alt="Text Size: " width="50" height="18"><br>
  <a href="#" onclick="setActiveStyleSheet('smallfont',1);return false;"><img src="/g/icon_text_sm.gif"  alt="Smaller Text" width="18" height="18" title="Smaller Text"></a>
  <a href="#" onclick="setActiveStyleSheet('',1);return false;"        ><img src="/g/icon_text_med.gif" alt="Normal Text"  width="18" height="18" title="Normal Text"></a>
  <a href="#" onclick="setActiveStyleSheet('bigfont',1);return false;" ><img src="/g/icon_text_lg.gif"  alt="Larger Text"  width="18" height="18" title="Larger Text"></a>
  <p>
  <a href="https://www.facebook.com/Nordic.Optical.Telescope"><img src="/g/facebook_icon.svg"  alt="Facebook"   height="25" border="0"></a>
  <a href="https://bsky.app/profile/nordictelescope.bsky.social">     <img src="/g/bluesky_icon.svg"   alt="Bluesky"    height="25" border="0"></a>
  <p>
  <a href="https://www.instagram.com/nordictelescope/">               <img src="/g/instagram_icon.svg" alt="Instagram"  height="25" border="0"></a>
  <a href="https://www.youtube.com/channel/UCmKqL1P0wjiR7UT_s6H9jVQ"><img src="/g/youtube_icon.svg"   alt="YouTube"    height="25" border="0"></a>
</td>

<td valign="top" align="left" bgcolor="#ffffff" width="100%" class="bodyline">
<table cellpadding="10" border="0" width="100%" height="100%">
<tr>
<td valign="top" width="100%">

<script language="JavaScript" type="text/javascript">document.title="NOTBot – NOT AI Assistant";</script>

<div class="bg-orb orb-a"></div>
<div class="bg-orb orb-b"></div>

<main class="shell">
  <header class="hero">
    <p class="kicker">NOT AI Assistant</p>
    <div class="health-bar"><span class="health-dot" id="healthDot"></span><span class="health-text" id="healthText"></span></div>
    <div class="hero-image-wrap">
      <img class="hero-image" src="./assets/not-observatory.jpg" alt="Nordic Optical Telescope above clouds">
      <!-- <img class="brand-logo overlay-top-left" src="./assets/notbot.png" alt="NOT logo"> -->
      <img class="notbot-logo overlay-top-left" src="./assets/notbot.png" alt="NOTBot logo">
    </div>
  </header>

  <section id="chatPanel" class="card chat-panel hidden">
    <div id="chatThread" class="chat-thread"></div>
  </section>

  <section class="ask-panel card">
    <label class="field">
      <textarea id="questionInput" rows="3" placeholder="Ask a question about NOT… type a follow-up to continue the conversation."></textarea>
    </label>
    <div class="actions">
      <button id="askBtn" class="btn-primary">Ask</button>
      <button id="clearBtn" class="btn-ghost">New Conversation</button>
      <span id="status" class="status" style="margin-left:auto">Idle</span>
    </div>
  </section>

  <section class="card history-card">
    <div class="sources-head">
      <h2>Session History</h2>
      <span id="historyCount" class="pill">0 items</span>
    </div>
    <div id="historyList" class="history-list"></div>
  </section>
</main>

<script src="./app.js?v=<?php echo filemtime(__DIR__ . '/app.js'); ?>" defer></script>

<!-- GDPR notice -->
<p style="font-size:12px;color:#666;margin:0 0 8px;max-width:1080px;margin-left:auto;margin-right:auto;text-align:center;line-height:1.4;">
  <strong>Privacy:</strong> All conversations are logged to improve the quality of future answers (RAG system training).
  Please use the 👍 / 👎 buttons on each answer — your feedback is essential for identifying and correcting poor responses.
</p>

<?php
if (defined('NOTBOT_FOOTER_PATH') && NOTBOT_FOOTER_PATH !== '' && is_file(NOTBOT_FOOTER_PATH)) {
  include(NOTBOT_FOOTER_PATH);
}
?>
