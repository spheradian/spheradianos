# Show the boot problem report, if there is one, at every login.
# The report is printed on the console once, when the problem is found; that
# text can scroll away or be on another terminal. Repeating it at each login
# makes sure a boot problem is never silently lost.
xsphereos_boot_report="${XSPHERE_REPORT:-/run/xsphereos/boot-report}"
if [ -r "$xsphereos_boot_report" ]; then
	cat "$xsphereos_boot_report"
fi
unset xsphereos_boot_report
