# Show the boot problem report, if there is one, at every login.
# The console is cleared before the login prompt, so text printed during boot
# can scroll away; this makes sure a boot problem is never silently lost.
xsphereos_boot_report="${XSPHERE_REPORT:-/run/xsphereos/boot-report}"
if [ -r "$xsphereos_boot_report" ]; then
	cat "$xsphereos_boot_report"
fi
unset xsphereos_boot_report
