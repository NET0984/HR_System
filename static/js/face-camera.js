/*
 * Chụp khuôn mặt bằng webcam.
 * - Chấm công (data-auto-capture): đếm ngược rồi chụp 1 ảnh và gửi.
 * - Đăng ký (data-auto-series): chụp lần lượt tối đa N ảnh, mỗi ảnh cách
 *   vài giây, rồi gửi tất cả.
 * Không lưu ảnh trên máy chủ: khung hình chỉ được gửi trong form.
 */
(function () {
    var root = document.querySelector('[data-face-camera]');
    if (!root) {
        return;
    }

    var form = root.querySelector('form');
    var video = root.querySelector('video');
    var canvas = root.querySelector('canvas');
    var input = root.querySelector('input[type="file"]');
    var startButton = root.querySelector('[data-face-start]');
    var captureButton = root.querySelector('[data-face-capture]');
    var stopButton = root.querySelector('[data-face-stop]');
    var status = root.querySelector('[data-face-status]');

    var autoSingle = root.hasAttribute('data-auto-capture');
    var autoSeries = root.hasAttribute('data-auto-series');
    var autoSeconds = Math.max(1, parseInt(root.dataset.autoSeconds || '4', 10) || 4);
    var intervalSeconds = Math.max(1, parseInt(root.dataset.intervalSeconds || '3', 10) || 3);
    var maxShots = Math.max(1, parseInt(root.dataset.maxShots || '5', 10) || 5);

    var stream = null;
    var countdownTimer = null;
    var seriesTimer = null;
    var capturing = false;
    var capturedFiles = [];

    function setStatus(text) {
        if (status) {
            status.textContent = text;
        }
    }

    function clearTimers() {
        if (countdownTimer) {
            clearInterval(countdownTimer);
            countdownTimer = null;
        }
        if (seriesTimer) {
            clearTimeout(seriesTimer);
            seriesTimer = null;
        }
    }

    function stopCamera() {
        clearTimers();
        if (stream) {
            stream.getTracks().forEach(function (track) {
                track.stop();
            });
            stream = null;
        }
        video.srcObject = null;
        video.hidden = true;
        if (stopButton) {
            stopButton.hidden = true;
        }
        if (captureButton) {
            captureButton.hidden = true;
        }
    }

    function resetCamera() {
        stopCamera();
        capturing = false;
        startButton.hidden = false;
        startButton.disabled = false;
    }

    function syncInputFiles() {
        var transfer = new DataTransfer();
        capturedFiles.forEach(function (file) {
            transfer.items.add(file);
        });
        input.files = transfer.files;
    }

    function grabFrame(callback) {
        if (!stream || !video.videoWidth) {
            callback(null);
            return;
        }
        var width = 320;
        var height = Math.round(width * video.videoHeight / video.videoWidth);
        canvas.width = width;
        canvas.height = height;
        canvas.getContext('2d').drawImage(video, 0, 0, width, height);
        canvas.toBlob(function (blob) {
            if (!blob) {
                callback(null);
                return;
            }
            var name = 'face-' + (capturedFiles.length + 1) + '.jpg';
            callback(new File([blob], name, { type: 'image/jpeg' }));
        }, 'image/jpeg', 0.9);
    }

    function submitForm() {
        setStatus('Đang xử lý...');
        if (form.requestSubmit) {
            form.requestSubmit();
        } else {
            form.submit();
        }
    }

    function captureOnce() {
        if (capturing) {
            return;
        }
        capturing = true;
        grabFrame(function (file) {
            if (!file) {
                capturing = false;
                setStatus('Không chụp được ảnh, vui lòng thử lại.');
                return;
            }
            capturedFiles = [file];
            syncInputFiles();
            stopCamera();
            submitForm();
        });
    }

    function captureSeriesShot() {
        setStatus('Đang chụp ' + (capturedFiles.length + 1) + '/' + maxShots + '...');
        grabFrame(function (file) {
            if (!file) {
                resetCamera();
                setStatus('Không chụp được ảnh. Vui lòng thử lại.');
                return;
            }
            capturedFiles.push(file);
            syncInputFiles();

            if (capturedFiles.length >= maxShots) {
                stopCamera();
                setStatus('Đã chụp ' + capturedFiles.length + ' ảnh. Đang gửi...');
                submitForm();
                return;
            }

            setStatus(
                'Đã chụp ' + capturedFiles.length + '/' + maxShots +
                '. Chụp tiếp sau ' + intervalSeconds + ' giây...'
            );
            seriesTimer = setTimeout(captureSeriesShot, intervalSeconds * 1000);
        });
    }

    function startSeries() {
        setStatus(
            'Chuẩn bị chụp ' + maxShots + ' ảnh, mỗi ảnh cách ' +
            intervalSeconds + ' giây...'
        );
        seriesTimer = setTimeout(captureSeriesShot, intervalSeconds * 1000);
    }

    function startSingleCountdown() {
        var remaining = autoSeconds;
        setStatus('Đang nhận diện... ' + remaining + 's');
        countdownTimer = setInterval(function () {
            remaining -= 1;
            if (remaining > 0) {
                setStatus('Đang nhận diện... ' + remaining + 's');
            } else {
                clearTimers();
                captureOnce();
            }
        }, 1000);
    }

    function startCamera() {
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
            setStatus('Trình duyệt không hỗ trợ camera. Vui lòng dùng trình duyệt khác.');
            return;
        }

        capturedFiles = [];
        capturing = false;
        startButton.disabled = true;

        navigator.mediaDevices.getUserMedia({
            video: { facingMode: 'user', width: { ideal: 640 }, height: { ideal: 480 } },
            audio: false
        }).then(function (mediaStream) {
            stream = mediaStream;
            video.srcObject = stream;
            video.hidden = false;
            startButton.hidden = true;
            if (stopButton) {
                stopButton.hidden = false;
            }

            var begin = function () {
                if (autoSeries) {
                    startSeries();
                } else if (autoSingle) {
                    startSingleCountdown();
                } else if (captureButton) {
                    captureButton.hidden = false;
                    setStatus('Đưa khuôn mặt vào giữa khung rồi bấm chụp.');
                }
            };

            if (video.readyState >= 2) {
                begin();
            } else {
                video.addEventListener('loadedmetadata', begin, { once: true });
            }
        }).catch(function (error) {
            startButton.disabled = false;
            var reason = error && error.name ? error.name : 'không xác định';
            setStatus('Không mở được camera (' + reason + '). Vui lòng thử lại.');
        });
    }

    startButton.addEventListener('click', startCamera);
    if (captureButton) {
        captureButton.addEventListener('click', captureOnce);
    }
    if (stopButton) {
        stopButton.addEventListener('click', resetCamera);
    }
    window.addEventListener('pagehide', stopCamera);
})();
