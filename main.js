const electron = require('electron');
const {app} = electron;
const {BrowserWindow} = electron;

let win;

function createWindow() {
    const clrkio = __dirname + '/clrkio.py';
    const spawn = require('child_process').spawn;
    const backend = spawn('C:\\Users\\william.jackson\\Pythons\\clrkio\\Scripts\\python.exe', [clrkio]);
    backend.stdout.on('data', (data) => {
        console.log('backend stdout: ' + data);
    });
    backend.stderr.on('data', (data) => {
        console.log('backend stderr: ' + data);
    });
    win = new BrowserWindow({width: 800, height: 600});
    win.loadURL('file://' + __dirname + '/pre_index.html');
    win.on('closed', () => {
        win = null;
        backend.kill('SIGINT');
    });
}

app.on("window-all-closed", function() {
  app.quit();
});

app.on('ready', createWindow);
