// Webhook configuration and handlers

// EASY SECRET #7: Slack webhook URL
const SLACK_WEBHOOK = "https://hooks.slack.com/services/T00000000/B00000000/XXXXXXXXXXXXXXXXXXXX";

function sendSlackNotification(message) {
    fetch(SLACK_WEBHOOK, {
        method: 'POST',
        body: JSON.stringify({ text: message })
    });
}

module.exports = { sendSlackNotification };
