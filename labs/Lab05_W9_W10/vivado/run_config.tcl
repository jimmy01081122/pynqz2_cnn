# Vivado batch runner for one of the four self-contained Lab05 configurations.
# Usage:
#   vivado -mode batch -source vivado/run_config.tcl -tclargs dense_int8
# Standard Tcl smoke test (does not call Vivado commands):
#   SMOKE_ONLY=1 tclsh vivado/run_config.tcl dense_int8

set script_dir [file normalize [file dirname [info script]]]
set lab_dir [file normalize [file join $script_dir ".."]]

if {$argc != 1} {
    puts stderr "Usage: run_config.tcl {dense_int8|dense_int4|int8_2to4|int4_2to4}"
    exit 2
}
set requested_config [lindex $argv 0]
if {![regexp {^[a-z0-9_]+$} $requested_config]} {
    puts stderr "Invalid config id: $requested_config"
    exit 2
}
set config_file [file join $script_dir "configs" [format "%s.tcl" $requested_config]]
if {![file isfile $config_file]} {
    puts stderr "Unknown config: $requested_config"
    exit 2
}
source $config_file

foreach variable_name {config_id display_name data_width enable_2to4 sparsity target_clock_ns} {
    if {![info exists $variable_name]} {
        puts stderr "Config is missing variable: $variable_name"
        exit 2
    }
}
if {$config_id ne $requested_config} {
    puts stderr "Config id mismatch: requested=$requested_config file=$config_id"
    exit 2
}
if {$data_width ni {4 8} || $enable_2to4 ni {0 1}} {
    puts stderr "Invalid configuration values"
    exit 2
}

proc find_rtl_files {directory} {
    set result {}
    foreach path [glob -nocomplain -directory $directory *] {
        if {[file isdirectory $path]} {
            set result [concat $result [find_rtl_files $path]]
        } elseif {[string tolower [file extension $path]] in {.sv .v}} {
            lappend result [file normalize $path]
        }
    }
    return [lsort -unique $result]
}

set part "xc7z020clg400-1"
if {[info exists ::env(FPGA_PART)] && $::env(FPGA_PART) ne ""} {
    set part $::env(FPGA_PART)
}
set top "ai_accel_top"
if {[info exists ::env(TOP)] && $::env(TOP) ne ""} {
    set top $::env(TOP)
}
if {![regexp {^[A-Za-z_][A-Za-z0-9_$]*$} $top]} {
    error "Invalid TOP module name: $top"
}
set rtl_dir [file join $lab_dir "rtl"]
if {[info exists ::env(RTL_DIR)] && $::env(RTL_DIR) ne ""} {
    set rtl_dir [file normalize $::env(RTL_DIR)]
}
set build_root [file join $lab_dir "build"]
if {[info exists ::env(BUILD_DIR)] && $::env(BUILD_DIR) ne ""} {
    set build_root [file normalize $::env(BUILD_DIR)]
}

if {![file isdirectory $rtl_dir]} {
    error "RTL directory not found: $rtl_dir"
}
set rtl_files [find_rtl_files $rtl_dir]
if {[llength $rtl_files] == 0} {
    error "No .sv or .v files found below $rtl_dir"
}

# Fail during the cheap Tcl smoke test if TOP is absent, rather than waiting for
# Vivado synthesis. This is a textual declaration check, not an HDL parser.
set top_found 0
set top_pattern [format {(^|[\n\r])[ \t]*module[ \t]+%s([ \t\r\n#;(]|$)} $top]
foreach rtl_file $rtl_files {
    set handle [open $rtl_file "r"]
    set source_text [read $handle]
    close $handle
    if {[regexp -- $top_pattern $source_text]} {
        set top_found 1
        break
    }
}
if {!$top_found} {
    error "TOP module '$top' was not found below RTL_DIR=$rtl_dir"
}

set xdc_file [file join $lab_dir "constraints" "lab05_timing.xdc"]
if {![file isfile $xdc_file]} {
    error "XDC not found: $xdc_file"
}

puts "============================================================"
puts "Lab05 configuration: $display_name"
puts "config_id=$config_id DATA_WIDTH=$data_width ENABLE_2TO4=$enable_2to4"
puts "part=$part top=$top"
puts "RTL_DIR=$rtl_dir"
puts "target_clock_ns=$target_clock_ns"
puts "============================================================"

if {[info exists ::env(SMOKE_ONLY)] && $::env(SMOKE_ONLY) eq "1"} {
    puts "SMOKE PASS: config, default RTL_DIR, TOP declaration, and XDC were found."
    exit 0
}

set run_dir [file join $build_root $config_id]
set project_dir [file join $run_dir "project"]
set report_dir [file join $run_dir "reports"]
file mkdir $project_dir
file mkdir $report_dir

create_project -force ppa_$config_id $project_dir -part $part
set_property target_language Verilog [current_project]
foreach rtl_file $rtl_files {
    if {[string tolower [file extension $rtl_file]] eq ".sv"} {
        read_verilog -sv $rtl_file
    } else {
        read_verilog $rtl_file
    }
}
set ::LAB_TARGET_CLOCK_NS $target_clock_ns
read_xdc $xdc_file

set generics [list DATA_WIDTH=$data_width ENABLE_2TO4=$enable_2to4]
# This is a block-level PPA experiment, not a pin-level board top. OOC mode
# prevents Vivado from inserting hundreds of I/O buffers for the intentionally
# wide teaching interface, while still allowing opt/place/route and reports.
synth_design -top $top -part $part -mode out_of_context -generic $generics
opt_design
place_design
phys_opt_design
route_design

report_utilization -hierarchical -file [file join $report_dir "utilization.rpt"]
report_timing_summary -delay_type max -max_paths 10 -report_unconstrained \
    -file [file join $report_dir "timing_summary.rpt"]
report_power -file [file join $report_dir "power.rpt"]
write_checkpoint -force [file join $run_dir "routed.dcp"]

set metadata_path [file join $run_dir "run_metadata.csv"]
set metadata [open $metadata_path "w"]
puts $metadata "config,data_width,sparsity,target_clock_ns,part,top,status"
puts $metadata "$config_id,$data_width,$sparsity,$target_clock_ns,$part,$top,vivado_completed"
close $metadata

puts "Vivado reports: $report_dir"
puts "Metadata: $metadata_path"
puts "Run completed. Preserve the original reports with your submitted CSV."
close_project
exit 0
