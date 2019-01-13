#!/usr/bin/env python

import os
import argparse
import functions
import itertools

from pathlib import Path
import numpy as np


def listdir_nohidden(path):
    for f in os.listdir(path):
        if not f.startswith('.'):
            yield f

            
def number_to_str(n):
    if n > 1000:
        return "{0:.4e}".format(n)
    else:
        return "{0:.2f}".format(n)


def print_table(results):
    print("Function &Best &Worst &Median &$c$ &$\\bar\{v\}$ &Mean &Std & FRate\\\\")
    print("\\midrule")
    for k, v in results.items():
        print("{0} &{1}({2}) &{3}({4}) &{5}({6}) &{7} &{8} &{9} &{10} &{11}\\\\".format(k, 
                                                                                         number_to_str(v['best_perf']), 
                                                                                         v['best_consts'], 
                                                                                         number_to_str(v['worst_perf']), 
                                                                                         v['worst_consts'], 
                                                                                         number_to_str(v['median_perf']),
                                                                                         v['median_consts'],
                                                                                         tuple(v['c']),
                                                                                         number_to_str(v['v']),
                                                                                         number_to_str(v['mean']),
                                                                                         number_to_str(v['std']),
                                                                                         v['f_rate']
                                                                                         ))


def print_table_rev(results):
    key_order = [("best_perf", "Best"), ("worst_perf", "Worst"), ("median_perf", "Median"), ("c", "$c$"), ("v", "$\\bar{v}$"), ("mean", "Mean"), ("std", "Std"), ("f_rate", "F Rate")]
    print("\\begin{tabular}{c|cccc}")
    print("\\toprule")
    print("&" + "&".join(results.keys()) + "\\\\")
    print("\\midrule")
    for k, n in key_order:
        if k == "best_perf":
            to_print = [f"{h[0]}({h[1]})" for h in list(zip([str(d["best_perf"]) for d in results.values()], [str(d["best_consts"]) for d in results.values()]))]
            print(n + "&" + "&".join(to_print) + "\\\\")
        elif k == "worst_perf":
            to_print = [f"{h[0]}({h[1]})" for h in list(zip([str(d["worst_perf"]) for d in results.values()], [str(d["worst_consts"]) for d in results.values()]))]
            print(n + "&" + "&".join(to_print) + "\\\\")
        else:
            print(n + "&" + "&".join([str(d[k]) for d in results.values()]) + "\\\\")
    print("\\bottomrule")
    print("\\end{tabular}")

        
def main(logdir_path, dimensions):
    logdir = Path(logdir_path)
    results = dict()
    for c in sorted(listdir_nohidden(logdir)):
        runs = len(list(listdir_nohidden(logdir / c)))
        best_list = list()
        idx_best_list = list()
        performances = np.array([])

        function_class = getattr(functions, c)
        function_obj = function_class(dimensions=dimensions)

        # feasibility rate
        fes = 0
        for r in listdir_nohidden(logdir / c):
            if r == "plots":
                continue
            s = np.load(logdir / c/ r / "solutions.npy")
            p = np.load(logdir / c / r / "performances.npy")
            if len(performances) == 0:
                performances = np.array([p])
                solutions = np.array([s])
            else:
                performances = np.concatenate([performances, [p]], axis=0)
                solutions = np.concatenate([solutions, [s]], axis=0)

            # take best of this run
            idx_best = np.unravel_index(np.nanargmin(p), p.shape)
            idx_best_list.append(idx_best)
            best_list.append(p[idx_best])

            feasible_solution = False
            # check if there is at least one feasible solution in this run to compute the feasible rate
            # get all positions where there might be feasible solutions (0 for g and 0/1 for h constraints)
            consts = list(function_class.constraints(None).keys())
            combinations = list(map(list, itertools.product([0, 1], repeat=len(consts))))
            for i, comb in enumerate(combinations):
                for const, (k, item) in zip(consts, enumerate(comb)):
                    if const.startswith('g'):
                        combinations[i][k] = 0
            # remove duplicates
            combinations.sort()
            feasible_indexes = list(l for l,_ in itertools.groupby(combinations))
            for f_idx in feasible_indexes:
                if p[tuple(f_idx)] != np.inf:
                    feasible_solution = True
            if feasible_solution:
                fes += 1

        performances[performances == np.inf] = np.nan

        # get the indexes over the entire data structure, because we need to know which constraints were violated
        best = np.min(best_list)
        idx_best =  np.unravel_index(np.where(performances.flatten() == best)[0][0], performances.shape)
        worst = np.max(best_list)
        idx_worst = np.unravel_index(np.where(performances.flatten() == worst)[0][0], performances.shape)
        idx_median = np.unravel_index(
            np.where(performances.flatten() == np.nanpercentile(performances,50,interpolation='nearest'))[0][0], 
            performances.shape
        )
        median = performances[idx_median]

        mean = np.mean(best_list)
        std = np.std(best_list)

        # compute # of violated constraints
        consts_best = 0
        consts_worst = 0
        consts_median = 0
        consts_median_specific = [0, 0, 0]
        mean_violations = list()
        for k, cost in enumerate(list(function_class.constraints(None).keys())):
            if cost.startswith('g'):
                if idx_best[k+1] > 0:
                    consts_best += 1
                if idx_worst[k+1] > 0:
                    consts_worst += 1
                if idx_median[k+1] > 0:
                    consts_median += 1
                    # add constraint violation to mean_violations
                    mean_violations.append(function_obj.constraints()[cost]['func'](solutions[idx_median]))

            if cost.startswith('h'):
                if idx_best[k+1] > 1:
                    consts_best += 1
                if idx_worst[k+1] > 1:
                    consts_worst += 1
                if idx_median[k+1] > 1:
                    consts_median += 1
                    # add constraint violation to mean_violations
                    mean_violations.append(function_obj.constraints()[cost]['func'](solutions[idx_median]))

            # violation > 0.0001
            if idx_median[k+1] == 2:
                consts_median_specific[0] += 1
            # violation > 0.01
            if idx_median[k+1] == 3:
                consts_median_specific[1] += 1
            # violation > 1.0
            if idx_median[k+1] == 4:
                consts_median_specific[2] += 1

#         assert sum(consts_median_specific) == consts_median

        results[c] = {
            "best_perf": round(best, 2),
            "best_consts": consts_best,
            "worst_perf": round(worst, 2),
            "worst_consts": consts_worst,
            "median_perf": round(median, 2),
            "median_consts": consts_median,
            "mean": round(mean, 2),
            "std": round(std, 2),
            "c": consts_median_specific,
            "v": round(np.mean(mean_violations), 2) if len(mean_violations) > 0 else 0,
            "f_rate": round(fes / runs, 2)
        }

    return results

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='MAP-Elites results aggregation')
    parser.add_argument('--logdir', type=str, help='Log directory', required=True)
    parser.add_argument('--dimensions', type=int, help='Dimensionality of evaluation function', required=True)
    args = parser.parse_args()
    results = main(args.logdir, args.dimensions)
    print_table(results)
