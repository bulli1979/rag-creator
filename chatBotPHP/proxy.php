<?php
// Buffer all output — prevents stray whitespace from PHP includes contaminating the JSON response.
ob_start();

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
#    ob_end_clean();
#    http_response_code(403);
#    header('Content-Type: application/json');
#    echo json_encode(['error' => 'Access denied']);
#    exit;
#}

// Only accept POST requests.
if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    ob_end_clean();
    http_response_code(405);
    header('Content-Type: application/json');
    echo json_encode(['error' => 'Method not allowed']);
    exit;
}

// Validate Content-Type.
$contentType = $_SERVER['HTTP_CONTENT_TYPE'] ?? $_SERVER['CONTENT_TYPE'] ?? '';
if (stripos($contentType, 'application/json') === false) {
    ob_end_clean();
    http_response_code(400);
    header('Content-Type: application/json');
    echo json_encode(['error' => 'Content-Type must be application/json']);
    exit;
}

// Read body with a 64 KB hard cap.
$body = file_get_contents('php://input', false, null, 0, 65537);
if (strlen($body) > 65536) {
    ob_end_clean();
    http_response_code(413);
    header('Content-Type: application/json');
    echo json_encode(['error' => 'Request body too large']);
    exit;
}

// Validate JSON.
$data = json_decode($body, true);
if ($data === null) {
    ob_end_clean();
    http_response_code(400);
    header('Content-Type: application/json');
    echo json_encode(['error' => 'Invalid JSON body']);
    exit;
}

// Determine target endpoint and HTTP method based on request type.
// Health checks use GET /api/health, chat requests use POST /api/chat.
// --- Logging endpoint ---
if (isset($data['action']) && $data['action'] === 'log') {
    ob_end_clean();

    if (!is_array($data['entries']) || empty($data['entries'])) {
        http_response_code(400);
        header('Content-Type: application/json');
        echo json_encode(['error' => 'entries array is required']);
        exit;
    }

    $logRoot = rtrim(NOTBOT_LOG_ROOT, '/');
    $monthDir = gmdate('Y-m');
    $logDir   = $logRoot . '/' . $monthDir;

    if (!is_dir($logDir)) {
        mkdir($logDir, 0750, true);
    }

    $files = ['conversations.log', 'good.log', 'bad.log'];
    $fpMap = [];
    foreach ($files as $f) {
        $path = $logDir . '/' . $f;
        $fh   = fopen($path, 'a');
        if ($fh === false) {
            http_response_code(500);
            header('Content-Type: application/json');
            echo json_encode(['error' => "Cannot open log file: $f"]);
            exit;
        }
        $fpMap[$f] = $fh;
    }

    $ids = [];
    foreach ($data['entries'] as $entry) {
        $logLine = [
            'ts'       => gmdate('c'),
            'id'       => bin2hex(random_bytes(8)),
            'q'        => mb_substr($entry['q'] ?? '', 0, 65535),
            'a'        => mb_substr($entry['a'] ?? '', 0, 131070),
            'feedback' => $entry['feedback'] ?? null,
        ];

        if (!empty($entry['id'])) {
            $logLine['id'] = $entry['id'];
        }
        if (!empty($entry['lang'])) {
            $logLine['lang'] = $entry['lang'];
        }
        if (!empty($entry['sources']) && is_array($entry['sources'])) {
            $logLine['sources'] = array_map(function($s) {
                // Sanitize each key/value; allow all string fields the backend returns.
                $clean = [];
                foreach ($s as $k => $v) {
                    $k = mb_substr((string) $k, 0, 64);
                    $clean[$k] = is_numeric($v) ? (float) $v : mb_substr((string) $v, 0, 2048);
                }
                return $clean;
            }, $entry['sources']);
        }

        fwrite($fpMap['conversations.log'], json_encode($logLine, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES) . "\n");
        $ids[] = $logLine['id'];

        if (!empty($entry['feedback'])) {
            $fbFile = ($entry['feedback'] === 'up') ? 'good.log' : 'bad.log';
            $fbLine = [
                'ts'      => gmdate('c'),
                'id'      => $logLine['id'],
                'q'       => mb_substr($entry['q'] ?? '', 0, 65535),
                'a'       => mb_substr($entry['a'] ?? '', 0, 131070),
            ];
            if (!empty($logLine['sources'])) {
                $fbLine['sources'] = $logLine['sources'];
            }
            fwrite($fpMap[$fbFile], json_encode($fbLine, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES) . "\n");
        }
    }

    foreach ($fpMap as $fh) { fclose($fh); }

    http_response_code(200);
    header('Content-Type: application/json');
    echo json_encode(['ok' => true, 'ids' => $ids]);
    exit;
}

// Chat proxy (original logic).
$endpoint = '/api/chat';
$method = 'POST';
if (isset($data['health_check']) && $data['health_check'] === true) {
    $endpoint = '/api/health';
    $method = 'GET';
}

$target = rtrim(NOTBOT_API_URL, '/') . $endpoint;

$context = stream_context_create([
    'http' => [
        'method'        => $method,
        'header'        => "Content-Type: application/json\r\n",
        'content'       => ($method === 'POST') ? $body : null,
        'timeout'       => 300,
        'ignore_errors' => true,
    ],
]);

$response = @file_get_contents($target, false, $context);

// Parse HTTP status from $http_response_header (set by file_get_contents).
$httpCode = 502;
if (!empty($http_response_header)) {
    foreach ($http_response_header as $h) {
        if (preg_match('#^HTTP/\S+\s+(\d+)#', $h, $m)) {
            $httpCode = (int) $m[1];
        }
    }
}

// Discard any buffered stray output before sending the JSON response.
ob_end_clean();
header('Content-Type: application/json');

if ($response === false) {
    http_response_code(502);
    echo json_encode(['error' => 'Backend unavailable']);
    exit;
}

http_response_code($httpCode ?: 502);
echo $response;
