set -euo pipefail

USERNAME=$(whoami)
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
AGENTS=~/Library/LaunchAgents

for plist in com.meetingbot.tray.plist com.meetingbot.worker.plist; do
    sed "s|YOUR_USERNAME|${USERNAME}|g; \
         s|/Users/${USERNAME}/meetingbot|${PROJECT_DIR}|g; \
         s|YOUR_HF_TOKEN_HERE|${HF_TOKEN:-}|g" \
        "${plist}" > "${AGENTS}/${plist}"
    echo "Installed: ${AGENTS}/${plist}"
done

launchctl load "${AGENTS}/com.meetingbot.tray.plist"
launchctl load "${AGENTS}/com.meetingbot.worker.plist"

echo ""
echo "Both LaunchAgents loaded. They will auto-start on next login."
echo ""
echo "Useful commands:"
echo "  launchctl list | grep meetingbot      # check running status"
echo "  launchctl stop  com.meetingbot.worker # stop worker manually"
echo "  launchctl start com.meetingbot.worker # start worker manually"
echo "  tail -f ~/meetings/worker.log         # live worker logs"
echo "  tail -f ~/meetings/tray.log           # live tray logs"