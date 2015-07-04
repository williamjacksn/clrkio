var backendAddress = "http://localhost:5000";

function checkBackend() {
    "use strict";
    var xhrIndex = new XMLHttpRequest();
    xhrIndex.onload = backendReady;
    xhrIndex.onerror = backendNotReady;
    xhrIndex.open("GET", backendAddress);
    xhrIndex.send();
}

function backendNotReady() {
    "use strict";
    console.log("Backend is not ready.");
    setTimeout(checkBackend, 500)
}

function backendReady() {
    "use strict";
    location.replace(backendAddress)
}

checkBackend();
