const consoleOutput = document.getElementById('console-output');
const botStatus = document.getElementById('bot-status');
const ramUsage = document.getElementById('ram-usage');

let lastLogSize = 0;

async function fetchLogs() {
    // Only fetch logs if the console is visible
    if (!consoleOutput) return;
    const url = `/bot/${userId}/${botIndex}/logs?size=${lastLogSize}`;
    const response = await fetch(url);
    if (response.ok) {
        const data = await response.json();
        if (data.log_data) {
            consoleOutput.textContent += data.log_data;
            consoleOutput.scrollTop = consoleOutput.scrollHeight;
        }
        lastLogSize = data.log_size;
    }
}

async function fetchStatus() {
    const url = `/bot/${userId}/${botIndex}/status`;
    const response = await fetch(url);
    if (response.ok) {
        const data = await response.json();
        botStatus.textContent = data.status;
        ramUsage.textContent = data.ram_usage + " MB";
        if (data.status === "RUNNING") {
            botStatus.className = 'running';
        } else {
            botStatus.className = '';
        }
    }
}

// Check if the status elements exist before fetching
if (botStatus && ramUsage) {
    // Initial fetches
    fetchStatus();
    fetchLogs();

    // Poll
    setInterval(fetchStatus, 5000);
    setInterval(fetchLogs, 3000);
}
