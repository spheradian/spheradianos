# shellcheck shell=sh
# Show the boot problem report, if there is one, at every login.
# The report is printed on the console once, when the problem is found; that
# text can scroll away or be on another terminal. Repeating it at each login
# makes sure a boot problem is never silently lost.
spheradianos_boot_report="${SPHERADIAN_REPORT:-/run/spheradianos/boot-report}"
if [ -r "$spheradianos_boot_report" ]; then
	cat "$spheradianos_boot_report"
fi
unset spheradianos_boot_report
