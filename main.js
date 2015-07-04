var app = require("app");
var browserWindow = require("browser-window");

require("crash-reporter").start();

var mainWindow = null;

app.on("window-all-closed", function() {
  app.quit();
});

app.on("ready", function() {
    var clrkio = __dirname + "/clrkio.py";
    var backend = require("child_process").spawn("python", [clrkio]);
    backend.stdout.on("data", function(data) {
        console.log("backend stdout: " + data);
    });
    backend.stderr.on("data", function(data) {
        console.log("backend stderr: " + data);
    });

    mainWindow = new browserWindow({width: 800, height: 600});
    mainWindow.loadUrl("file://" + __dirname + "/pre_index.html");

    // Open developer tools
    // mainWindow.openDevTools();

    // Emitted when the window is closed.
    mainWindow.on("closed", function() {
        mainWindow = null;
        backend.kill("SIGINT");
    });
});
