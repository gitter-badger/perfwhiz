#!/usr/bin/env python
#
# Alec Hothan
# ---------------------------------------------------------


from optparse import OptionParser
import sys
import os.path
import re, glob
import itertools
#
# Import reusable code from pnstk.py
#

import marshal
import zlib
import pandas

from bokeh.plotting import figure, output_file, show
from bokeh.models.sources import ColumnDataSource
from pandas import DataFrame

# Global variables

# start analysis after first from_time usec
from_time = 0
# cap input file to first cap_time usec, 0 = unlimited
cap_time = 0

# KVM exit reasons
# Intel64 and IA32 Architecture Software Developer's Manual Vol 3B, System Programming Guide Part 2
# Appendix I
KVM_EXIT_REASONS = [
    'Exception or NMI',     # 0
    'External Interrupt',
    'Triple Fault',
    'INIT',
    'Startup IPI',
    'I/O SMI (System Management Interrupt)',
    'Other SMI',
    'Interrupt Window',
    'NMI window',
    'Task Switch',
    'CPUID',                # 10
    'GETSEC',
    'HLT',                   # 12
    'INVD',
    'INVLPG',
    'RDPMC',
    'RDTSC',
    'RSM',
    'VMCALL',
    'VMCLEAR',
    'VMLAUNCH',             #20
    'VMPTRLD',
    'VMPTRST',
    'VMREAD',
    'VMRESUME',
    'VMWRITE',
    'VMXOFF',
    'VMXON',
    'Control Register Access',
    'MOV DR',
    'I/O Instruction',      #30
    'RDMSR',
    'WRMSR',
    'VM Entry Failure (invalid guest state)',
    'VM Entry Failure (MSR loading)',
    'n/a 35',
    'MWAIT',
    'Monitor trap flag',
    'n/a 38',
    'MONITOR',
    'PAUSE',                #40
    'VM Entry Failure (machine check)',
    'n/a 42',
    'TPR below threshold',
    'APIC Access',
    'n/a 45',
    'Access to GDTR or IDTR',
    'Access to LDTR or TR',
    'EPT violation',
    'EPT misconfiguration',
    'INVEPT',               # 50
    'RDTSCP',
    'VMX preemption timer expired',  # 52
    'INVVPID',
    'WBINVD',
    'XSETBV'
]
GREEN = "#5ab738"
RED =  "#f22c40"

DEFAULT_PALETTE = [ GREEN, RED, "#407ee7", "#df5320", "#00ad9c", "#c33ff3"]


def cycle_colors(chunk, palette=DEFAULT_PALETTE):
    """ Build a color list just cycling through a given palette.

    Args:
        chuck (seq): the chunk of elements to generate the color list
        palette (seq[color]) : a palette of colors to cycle through

    Returns:
        colors

    """
    colors = []

    g = itertools.cycle(palette)
    for i in range(len(chunk)):
        colors.append(next(g))

    return colors

def output_html(chart_type, tid_list=[]):
    filename = html_file + '_' + chart_type
    for tid in tid_list:
        filename += '_' + str(tid)
    filename += '.html'
    output_file(filename)
    print('Saved to ' + filename)

def show_tid_heatmap(df, tid):
    df = df[df['pid'] == tid]
    # these are the 2 main events to show
    legend_map = {
        'sched__sched_stat_sleep': (RED, 'wakeup from sleep (y=sleep time)'),
        'sched__sched_stat_runtime': (GREEN, 'switched out from cpu (y=run time)')
    }

    p = figure(plot_width=1000, plot_height=800, y_axis_type="log")
    p.xaxis.axis_label = 'time (usecs)'
    p.yaxis.axis_label = 'duration (usecs)'
    p.legend.orientation = "bottom_right"
    p.xaxis.axis_label_text_font_size = "10pt"
    p.yaxis.axis_label_text_font_size = "10pt"
    p.title = "Context switches tid %d" % (tid)
    p.ygrid.minor_grid_line_color = 'navy'
    p.ygrid.minor_grid_line_alpha = 0.1

    for event in legend_map:
        dfe = df[df.event == event]
        color, legend_text = legend_map[event]
        legend_text = '%s (%d)' % (legend_text, len(dfe))
        p.circle('usecs', 'duration', source=ColumnDataSource(dfe), size=5, color=color,
                 alpha=0.3,
                 legend=legend_text)

    # specify how to output the plot(s)
    output_html('thm', [tid])

    # display the figure
    show(p)

def convert_exit_df(df, label):
    # fill in the error reason text from the code in
    df.next_comm = df.next_comm.apply(lambda x: '(%02d) %s' % (x, KVM_EXIT_REASONS[x]))
    series_percent = df.next_comm.value_counts(normalize=True)
    series_count = df.next_comm.value_counts()
    series_percent = pandas.Series(["{0:.2f}%".format(val * 100) for val in series_percent], index=series_percent.index)

    series_percent.name = '%'
    series_count.name = label + ' count'

    res = pandas.concat([series_count, series_percent], axis=1)
    return res

def show_exit_type_count(df_all_exits, df_last_exits):

    res_all = convert_exit_df(df_all_exits, 'total')
    res_last = convert_exit_df(df_last_exits, 'last exit')
    res = pandas.concat([res_all, res_last], axis=1)
    res.fillna(0, inplace=True)
    res.sort('total count', inplace=True, ascending=False)
    print res

def show_kvm_heatmap(df, tid):
    df = df[df['pid'] == tid]
    # these are the 2 main events to show
    legend_map = {
        'kvm_entry': (RED, 'vcpu not running (y=kvm+sleep time)'),
        'kvm_exit': (GREEN, 'vcpu running (y=vcpu run time)')
    }

    p = figure(plot_width=1000, plot_height=800, y_axis_type="log")
    p.xaxis.axis_label = 'time (usecs)'
    p.yaxis.axis_label = 'duration (usecs)'
    p.legend.orientation = "bottom_right"
    p.xaxis.axis_label_text_font_size = "10pt"
    p.yaxis.axis_label_text_font_size = "10pt"
    p.title = "KVM entries and exits tid %d" % (tid)
    p.ygrid.minor_grid_line_color = 'navy'
    p.ygrid.minor_grid_line_alpha = 0.1
    for event in legend_map:
        dfe = df[df.event == event]
        color, legend_text = legend_map[event]
        legend_text = '%s (%d)' % (legend_text, len(dfe))
        # there is bug in bokeh when there are too many circles to draw, nothing is visible
        if len(dfe) > 50000:
            dfe = dfe[:50000]
            print 'Series for %s display truncated to 50000 events' % (event)
        p.circle('usecs', 'duration', source=ColumnDataSource(dfe), size=5, color=color,
                 alpha=0.3,
                 legend=legend_text)

    # specify how to output the plot(s)
    output_html('kvm', [tid])

    # display the figure
    show(p)

    # all exit types
    dfexits = df[df.event == 'kvm_exit']

    # now keep only the last exit before a switch
    # only keep kvm_exits and context switches
    df = df[(df['event'] == 'kvm_exit') | (df['event'] == 'sched__sched_switch')]

    # move all rows up
    sdf = df.shift(-1)
    # only keep rows that have a different event than their next row
    df = df[df['event'] != sdf['event']]
    # delete last row
    df = df.drop(df.tail(1).index)

    # delete all sched switches as they have served their purpose
    df = df[df['event'] == 'kvm_exit']

    show_exit_type_count(dfexits, df)


def show_cpu_locality(df, tids):
    tid_list = [int(x) for x in tids]
    df = df[df['pid'].isin(tid_list)]
    df = df[df['event'] == 'sched__sched_stat_runtime']

    p = figure(plot_width=1000, plot_height=800)
    p.xaxis.axis_label = 'time (usecs)'
    p.yaxis.axis_label = 'core'
    p.legend.orientation = "bottom_right"
    p.xaxis.axis_label_text_font_size = "10pt"
    p.yaxis.axis_label_text_font_size = "10pt"
    p.title = "Core locality"

    color_list = cycle_colors(tids)

    for tid, color in zip(tid_list, color_list):
        dfe = df[df['pid'] == tid]
        legend_text = 'tid %d (%d)' % (tid, len(dfe))
        p.circle('usecs', 'cpu', source=ColumnDataSource(dfe), size=6, color=color,
                 alpha=0.3,
                 legend=legend_text)

    # specify how to output the plot(s)
    output_html('cpuloc', tid_list)

    # display the figure
    show(p)

def show_successors(df, tid):
    # only look up those switch events related to this tid
    df = df[df['pid'] == tid]
    df = df[df['event'] == 'sched__sched_switch']
    # aggregate all the per core tasks (e.g. swapper/0 -> swapper)
    df['next_comm'] = df['next_comm'].str.replace(r'/.*$','')
    series_percent = df.next_comm.value_counts(normalize=True)
    series_count = df.next_comm.value_counts()
    series_percent = pandas.Series(["{0:.2f}%".format(val * 100) for val in series_percent], index=series_percent.index)

    series_percent.name = 'percent'
    series_count.name = 'count'
    print pandas.concat([series_count, series_percent], axis=1)

# ---------------------------------- MAIN -----------------------------------------

parser = OptionParser(usage="usage: %prog [options] <cdict_file>")

parser.add_option("-t", "--tid",
                  dest="tid",
                  help="show thread context switch heat map"
                  )
parser.add_option("--successors-of",
                  dest="successor_of_tid",
                  help="show list of successors of given tid"
                  )
parser.add_option("--show-tids",
                  dest="show_tids",
                  action="store_true",
                  default=False,
                  help="show list of all tids with event count)"
                  )
parser.add_option("--cpu-locality",
                  dest="cpu_loc",
                  action="append",
                  metavar="tid",
                  help="show cpu locality chart for given threads"
                  )
parser.add_option("--kvm-exits",
                  dest="kvm_exits",
                  metavar="tid",
                  help="show thread kvm exits heat map"
                  )
parser.add_option("-c", "--cap",
                  dest="cap_time",
                  help="(optional) cap the analysis to first <cap_time> msec of capture (default=all)"
                  )
parser.add_option("-f", "--from",
                  dest="from_time",
                  help="(optional) start the analysis after first <from_time> msec of capture (default=0)"
                  )
(options, args) = parser.parse_args()

'''
df = DataFrame(  {'AAA': [0, 0, 0, 1,2,3,4,5,6,7,8,9,10],
                  'tid': [0, 0, 5, 5,5,5,5,5,5,5,5,5,5],
                  'next_comm': [0,0,0,0,44,0,12,0,0,0,0,0,0],
                  'event': ['any', 'kvm_exit',
                            'kvm_entry',
                            'kvm_exit','kvm_exit','sched__sched_switch',
                            'kvm_exit', 'sched__sched_switch',
                            'kvm_exit', 'kvm_exit', 'kvm_exit', 'sched__sched_switchB', 'kvm_exit']})
show_last_exit_reasons_before_switches(df, 5)
sys.exit(0)
'''

if options.from_time:
    from_time = int(options.from_time) * 1000
if options.cap_time:
    # convert to usec
    cap_time = int(options.cap_time) * 1000 + from_time

if not args:
    print 'Missing cdict file'
    sys.exit(1)

cdict_file = args[0]
if not cdict_file.endswith('.cdict'):
    print('input file name must have the .cdict extension')

with open(cdict_file, 'r') as ff:
    cdict = ff.read()

perf_dict = marshal.loads(zlib.decompress(cdict))
df = DataFrame(perf_dict)
html_file = cdict_file.replace('.cdict', '')

# filter on usecs
if from_time:
    df = df[df['usecs'] >= from_time]
if cap_time:
    df = df[df['usecs'] <= cap_time]

if options.show_tids:
    res = df.groupby(['pid', 'task_name']).size()
    res.sort(ascending=False)
    print res
elif options.cpu_loc:
    show_cpu_locality(df, options.cpu_loc)
elif options.tid:
    show_tid_heatmap(df, int(options.tid))
elif options.kvm_exits:
    show_kvm_heatmap(df, int(options.kvm_exits))
elif options.successor_of_tid:
    show_successors(df, int(options.successor_of_tid))

