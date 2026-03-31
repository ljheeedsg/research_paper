"""
消融实验 B4：CMAB + 信任 + PGRD（移除 LGSC）
输出：expeiment2_b4_taskcover.json（0-23轮任务覆盖数）
"""

import json
import random
import math
from collections import defaultdict

# ========== 参数配置 ==========
RANDOM_SEED = 42
random.seed(RANDOM_SEED)

BUDGET = 5000
K = 10
R = 24
M_VERIFY = 7

ETA = 0.6
THETA_HIGH = 0.75
THETA_LOW = 0.3

ALPHA = 0.6
BETA = 0.4
ZETA = 1.2
LAMBDA = 1.8
SIGMA = 0.85
PSI_TH = 0.4
FEE = 2
MEMBER_VALIDITY = 6

MEMBER_RATIO = 0.9
MEMBER_MULTIPLIER = 1.8
NORMAL_MULTIPLIER = 1.0
MEMBER_COST_RANGE = (0.4, 0.6)
NORMAL_COST_RANGE = (0.7, 0.9)
PROFIT_RANGE = (1.2, 2.0)

SUNK_THRESHOLD = 20
MEMBER_BONUS = 20
RHO_INIT = 1.0

# ========== 工具函数 ==========
def load_json(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_json(data, filepath):
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

# ========== 第一阶段：数据准备 ==========
def parse_worker_segments(segments_by_region):
    workers = defaultdict(list)
    for region_key, seg_list in segments_by_region.items():
        region = int(region_key.split('_')[1])
        for seg in seg_list:
            vid = seg['vehicle_id']
            idx = vid.split('_')[1] if '_' in vid else vid
            workers[idx].append({
                'region_id': region,
                'start_time': seg['start_time'],
                'end_time': seg['end_time'],
                'cost': seg['cost'],
                'is_trusted': seg['is_trusted']
            })
    return workers

def parse_tasks(task_segments):
    tasks = []
    for region_key, task_list in task_segments.items():
        region = int(region_key.split('_')[1])
        for task in task_list:
            tasks.append({
                'task_id': task['task_id'],
                'region_id': region,
                'start_time': task['start_time'],
                'end_time': task['end_time'],
                'required_workers': task['required_workers']
            })
    return tasks

def generate_worker_options(workers, tasks):
    worker_options = []
    for worker_id, segs in workers.items():
        is_trusted = segs[0]['is_trusted']
        base_cost = segs[0]['cost']
        trust = 1.0 if is_trusted else 0.5
        category = 'trusted' if is_trusted else 'unknown'
        covered = []
        for task in tasks:
            for seg in segs:
                if seg['region_id'] != task['region_id']: continue
                if seg['start_time'] >= task['end_time'] or seg['end_time'] <= task['start_time']: continue
                quality = random.uniform(0, 1)
                task_data = random.uniform(0, 1)
                covered.append({
                    'task_id': task['task_id'],
                    'quality': quality,
                    'task_price': base_cost,
                    'start_time': max(seg['start_time'], task['start_time']),
                    'end_time': min(seg['end_time'], task['end_time']),
                    'task_start_time': task['start_time'],
                    'task_data': task_data
                })
                break
        worker_options.append({
            'worker_id': worker_id,
            'is_trusted': is_trusted,
            'trust': trust,
            'category': category,
            'total_cost': len(covered) * base_cost,
            'covered_tasks': covered
        })
    return worker_options

def generate_task_weights(tasks):
    return {task['task_id']: task['required_workers'] for task in tasks}

def generate_task_grid_map(task_segments):
    grid_map = []
    for region_key, task_list in task_segments.items():
        region_id = int(region_key.split('_')[1])
        for task in task_list:
            grid_map.append({'task_id': task['task_id'], 'grid_id': region_id})
    return grid_map

def generate_task_classification(worker_options_path, task_segments_path, output_path):
    data = load_json(worker_options_path)
    worker_options = data['worker_options']
    task_segments = load_json(task_segments_path)
    all_task_ids = []
    for region_key, tasks in task_segments.items():
        for task in tasks:
            all_task_ids.append(task['task_id'])
    task_prices = defaultdict(list)
    for w in worker_options:
        for task in w['covered_tasks']:
            task_prices[task['task_id']].append(task['task_price'])
    tasks_info = []
    default_price = 10.0
    for tid in all_task_ids:
        base_price = sum(task_prices[tid])/len(task_prices[tid]) if tid in task_prices else default_price
        tasks_info.append({'task_id': tid, 'base_price': base_price})
    tasks_info.sort(key=lambda x:x['base_price'], reverse=True)
    m = len(tasks_info)
    k = int(MEMBER_RATIO * m)
    final_tasks = []
    for idx, info in enumerate(tasks_info):
        tid = info['task_id']
        base_price = info['base_price']
        is_member = idx < k
        if is_member:
            tp = base_price * MEMBER_MULTIPLIER
            cost_ratio = random.uniform(*MEMBER_COST_RANGE)
        else:
            tp = base_price * NORMAL_MULTIPLIER
            cost_ratio = random.uniform(*NORMAL_COST_RANGE)
        wc = tp * cost_ratio
        si = tp * random.uniform(*PROFIT_RANGE)
        pi = tp - wc
        final_tasks.append({
            'task_id': tid, 'task_price': round(tp,2), 'worker_cost': round(wc,2),
            'system_income': round(si,2), 'pure_worker_income': round(pi,2),
            'type': 'member' if is_member else 'normal'
        })
    save_json(final_tasks, output_path)

def data_preparation(worker_segments_path, task_segments_path, out_worker, out_weight, out_grid, out_class):
    worker_segments = load_json(worker_segments_path)
    task_segments = load_json(task_segments_path)
    workers = parse_worker_segments(worker_segments)
    tasks = parse_tasks(task_segments)
    worker_options = generate_worker_options(workers, tasks)
    save_json({'worker_options': worker_options}, out_worker)
    task_weights = generate_task_weights(tasks)
    save_json({'task_weights': task_weights}, out_weight)
    task_grid = generate_task_grid_map(task_segments)
    save_json(task_grid, out_grid)
    generate_task_classification(out_worker, task_segments_path, out_class)
    lgsc_params = {'sunk_threshold': SUNK_THRESHOLD, 'member_bonus': MEMBER_BONUS, 'rho_init': RHO_INIT}
    save_json(lgsc_params, 'step9_lgsc_params.json')
    return worker_options, tasks, task_weights, task_grid

# ========== 第二阶段：初始化 ==========
def initialize_cmab(worker_path, weight_path, class_path, lgsc_path):
    data = load_json(worker_path)
    workers = data['worker_options']
    task_weights = load_json(weight_path)['task_weights']
    task_class = load_json(class_path)
    lgsc = load_json(lgsc_path)
    task_time_map = {}
    for w in workers:
        for t in w['covered_tasks']:
            if t['task_id'] not in task_time_map:
                task_time_map[t['task_id']] = t['task_start_time']
    for w in workers:
        w['n_i'] = len(w['covered_tasks'])
        w['avg_quality'] = sum(t['quality'] for t in w['covered_tasks'])/w['n_i'] if w['n_i']>0 else 0.0
        w['judge_count'] = 1
        w['hist_reward_m'] = 0.0
        w['hist_reward_n'] = 0.0
        w['available_rounds'] = set(t['task_start_time']//3600 for t in w['covered_tasks'])
        w['is_member'] = False
        w['member_until'] = -1
    Uc = set(w['worker_id'] for w in workers if w['category']=='trusted')
    Uu = set(w['worker_id'] for w in workers if w['category']=='unknown')
    Um = set()
    task_covered_count = {tid:0 for tid in task_time_map}
    required_workers = {tid:task_weights[tid] for tid in task_time_map}
    total_learned = sum(w['n_i'] for w in workers)
    member_prices = [t['task_price'] for t in task_class if t['type']=='member']
    normal_prices = [t['task_price'] for t in task_class if t['type']=='normal']
    Rm = sum(member_prices)/len(member_prices) if member_prices else 0
    Rn = sum(normal_prices)/len(normal_prices) if normal_prices else 0
    return workers, task_covered_count, required_workers, total_learned, Uc, Uu, Um, Rm, Rn, task_time_map

# ========== 第三阶段：核心函数（已移除 LGSC）==========
def ucb_quality(w, total):
    if w['n_i']==0: return 1.0
    return w['avg_quality'] + math.sqrt((K+1)*math.log(total)/w['n_i'])

def generate_validation_tasks(workers, tg_map, t_time, Uc, Uu, r, M):
    avail = [w for w in workers if r in w['available_rounds']]
    if not avail: return []
    grid_uc=defaultdict(int)
    grid_uu=defaultdict(int)
    grid_ts=defaultdict(set)
    for w in avail:
        for t in w['covered_tasks']:
            if t['task_start_time']//3600 != r: continue
            gid = tg_map.get(t['task_id'])
            if gid is None: continue
            grid_ts[gid].add(t['task_id'])
            if w['worker_id'] in Uc: grid_uc[gid]+=1
            elif w['worker_id'] in Uu: grid_uu[gid]+=1
    valid = [g for g in grid_uc if grid_uc[g]>0]
    valid.sort(key=lambda g:grid_uu.get(g,0), reverse=True)
    sel = valid[:M]
    return [random.choice(list(grid_ts[g])) for g in sel if grid_ts[g]]

def update_trust(workers, vtasks, tg_map, Uc, Uu, Um, r, eta, th, tl):
    avail = [w for w in workers if r in w['available_rounds']]
    for vt in vtasks:
        uc_data = []
        for w in avail:
            if w['worker_id'] in Uc:
                for t in w['covered_tasks']:
                    if t['task_id']==vt:
                        uc_data.append(t['task_data'])
                        break
        if not uc_data: continue
        base = sorted(uc_data)[len(uc_data)//2]
        for w in avail:
            wid = w['worker_id']
            if wid in Uu:
                dat = None
                for t in w['covered_tasks']:
                    if t['task_id']==vt:
                        dat = t['task_data']
                        break
                if dat is None: continue
                err = abs(dat-base)/base if base!=0 else abs(dat-base)
                w['trust'] = max(0, min(1, w['trust'] + eta*(1-2*err)))
                if w['trust']>=th:
                    Uc.add(wid); Uu.discard(wid); w['category']='trusted'
                elif w['trust']<=tl:
                    Um.add(wid); Uu.discard(wid); w['category']='malicious'
    return Uc, Uu, Um

def pgrd_decision(workers, task_class, Rm, Rn, r, fee, alpha, beta, zeta, lam, sig, psi_th):
    ttype = {t['task_id']:t['type'] for t in task_class}
    tcost = {t['task_id']:t['worker_cost'] for t in task_class}
    avail = [w for w in workers if r in w['available_rounds']]
    bid = {}
    new_mem=set()
    total_fee=0.0
    for w in avail:
        wid=w['worker_id']
        if w['category']=='malicious': continue
        mt, nt = [],[]
        for t in w['covered_tasks']:
            if t['task_start_time']//3600 != r: continue
            if ttype[t['task_id']]=='member': mt.append(t['task_id'])
            else: nt.append(t['task_id'])
        if w['is_member'] and w['member_until']>=r:
            bid[wid]=mt+nt; continue
        if not mt and not nt:
            bid[wid]=[]; continue
        if w['category']=='unknown':
            bid[wid]=nt; continue
        if not mt:
            bid[wid]=nt; continue
        bm = alpha*w['hist_reward_m'] + beta*Rm
        bn = alpha*w['hist_reward_n'] + beta*Rn
        dlt = Rm - Rn
        loss = lam*(dlt**sig) if dlt>0 else 0
        cm = sum(tcost[tid] for tid in mt)/len(mt)
        nn = len(nt)
        cn = sum(tcost[tid] for tid in nt)/nn if nn>0 else 0
        Um = len(mt)*(bm+loss-cm) - fee
        Un = len(nt)*(bn-cn) if nn>0 else -1e9
        Um = max(-100, min(100, Um))
        Un = max(-100, min(100, Un))
        psi = math.exp(zeta*Um)/(math.exp(zeta*Um)+math.exp(zeta*Un))
        if psi>=psi_th:
            new_mem.add(wid)
            if not w['is_member']:
                w['sunk_value']=0.0
                w['sunk_rate']=RHO_INIT
                w['bonus_count']=0
                w['last_period_cost']=0.0
            w['is_member']=True
            w['member_until']=r+MEMBER_VALIDITY
            bid[wid]=mt+nt
            total_fee+=fee
        else:
            bid[wid]=nt
    return bid, new_mem, total_fee

def cmab_round(workers, cover, req, rem_bug, K, total_l, r, bid):
    cand = [w for w in workers if r in w['available_rounds'] and w['category']!= 'malicious' and bid.get(w['worker_id'])]
    if not cand: return [], rem_bug, cover, total_l, 0.0, []
    sel=[]; cost=0.0; comp=[]
    for _ in range(K):
        if not cand: break
        best=-1; bw=None; bt=None
        for w in cand:
            tl = [tid for tid in bid[w['worker_id']] if cover[tid]<req[tid]]
            if not tl: continue
            c = len(tl)*w['covered_tasks'][0]['task_price']
            if c>rem_bug: continue
            q = ucb_quality(w, total_l)
            g = sum(req[tid]*q for tid in tl)
            rat = g/c if g>0 else 0
            if rat>best: best=rat; bw=w; bt=tl
        if bw is None: break
        sel.append(bw['worker_id'])
        c = len(bt)*bw['covered_tasks'][0]['task_price']
        cost+=c
        rem_bug -=c
        comp.append((bw, bt))
        for tid in bt: cover[tid]+=1
        lnum = len(bt)
        if lnum>0:
            bw['n_i'] += lnum
            qmap = {t['task_id']:t['quality'] for t in bw['covered_tasks']}
            obs = sum(qmap[tid] for tid in bt)/lnum
            prev = bw['avg_quality']*(bw['n_i']-lnum)
            bw['avg_quality'] = (prev + obs*lnum)/bw['n_i']
            total_l += lnum
        cand.remove(bw)
    return sel, rem_bug, cover, total_l, cost, comp

def update_history(workers, comp, task_class):
    ttype = {t['task_id']:t['type'] for t in task_class}
    tprice = {t['task_id']:t['task_price'] for t in task_class}
    tm, tn, cntm, cntn =0,0,0,0
    for w, tl in comp:
        mm, nn = [],[]
        for tid in tl:
            p = tprice[tid]
            if ttype[tid]=='member':
                mm.append(p); tm+=p; cntm+=1
            else:
                nn.append(p); tn+=p; cntn+=1
        w['hist_reward_m'] = sum(mm)/len(mm) if mm else 0
        w['hist_reward_n'] = sum(nn)/len(nn) if nn else 0
    Rm = tm/cntm if cntm>0 else 0
    Rn = tn/cntn if cntn>0 else 0
    return Rm, Rn

# ========== 主循环：B4（无LGSC）==========
def greedy_recruitment(workers, cover, req, total_l, Uc, Uu, Um, Rm, Rn, B, K, R, tg_map, t_time, M, eta, th, tl, pgrd_p, task_class):
    rem_bug = B
    total_cost=0
    sel=[]
    rounds=0
    total_fee=0
    details=[]
    cover_records=[]
    total_task = len(req)

    for r in range(R):
        print(f"--- 轮次 {r} (B4：无LGSC) ---")
        avail = [w for w in workers if r in w['available_rounds']]
        if not avail:
            c = sum(1 for tid,v in cover.items() if v>=req[tid])
            cover_records.append({'round':r,'completed':c,'total':total_task,'rate':c/total_task})
            continue

        minc = min(w['total_cost'] for w in avail)
        if rem_bug < minc:
            c = sum(1 for tid,v in cover.items() if v>=req[tid])
            cover_records.append({'round':r,'completed':c,'total':total_task,'rate':c/total_task})
            for rr in range(r+1,R):
                cover_records.append({'round':rr,'completed':c,'total':total_task,'rate':c/total_task})
            break

        if all(v>=req[tid] for tid,v in cover.items()):
            c = sum(1 for tid,v in cover.items() if v>=req[tid])
            cover_records.append({'round':r,'completed':c,'total':total_task,'rate':c/total_task})
            for rr in range(r+1,R):
                cover_records.append({'round':rr,'completed':c,'total':total_task,'rate':c/total_task})
            break

        bid, new_mem, fee = pgrd_decision(workers, task_class, Rm, Rn, r,
            pgrd_p['fee'], pgrd_p['alpha'], pgrd_p['beta'],
            pgrd_p['zeta'], pgrd_p['lam'], pgrd_p['sigma'], pgrd_p['psi_th'])
        total_fee += fee

        vts = generate_validation_tasks(workers, tg_map, t_time, Uc, Uu, r, M)
        sel_r, rem_bug, cover, total_l, cost_r, comp = cmab_round(workers, cover, req, rem_bug, K, total_l, r, bid)
        total_cost += cost_r
        if sel_r:
            sel.extend(sel_r)
            rounds +=1

        if vts:
            Uc, Uu, Um = update_trust(workers, vts, tg_map, Uc, Uu, Um, r, eta, th, tl)
        Rm, Rn = update_history(workers, comp, task_class)

        c = sum(1 for tid,v in cover.items() if v>=req[tid])
        print(f"完成任务 {c}/{total_task} | 可信 {len(Uc)} 未知 {len(Uu)} 恶意 {len(Um)}")
        cover_records.append({'round':r,'completed':c,'total':total_task,'rate':c/total_task})

    # ========== 输出 B4 任务覆盖文件 ==========
    save_json(cover_records, 'expeiment2_b4_taskcover.json')
    print("\n✅ B4（无LGSC）任务覆盖数据已保存：expeiment1_B4_taskcover.json")

    return {
        'covered': sum(1 for tid,v in cover.items() if v>=req[tid]),
        'Uc': len(Uc), 'Um': len(Um), 'Uu': len(Uu),
        'cost': total_cost, 'cover_records': cover_records
    }

# ========== 主函数 ==========
def main():
    WORKER = 'step6_worker_segments.json'
    TASK = 'step6_task_segments.json'
    WO = 'step9_worker_option_set.json'
    TW = 'step9_task_weight_list.json'
    TG = 'step9_tasks_grid_num.json'
    TC = 'step9_tasks_classification.json'

    data_preparation(WORKER, TASK, WO, TW, TG, TC)
    workers, cover, req, total_l, Uc, Uu, Um, Rm, Rn, t_time = initialize_cmab(WO, TW, TC, 'step9_lgsc_params.json')
    tg_map = {item['task_id']:item['grid_id'] for item in load_json(TG)}
    pgrd_p = {'fee':FEE,'alpha':ALPHA,'beta':BETA,'zeta':ZETA,'lam':LAMBDA,'sigma':SIGMA,'psi_th':PSI_TH}
    res = greedy_recruitment(workers, cover, req, total_l, Uc, Uu, Um, Rm, Rn, BUDGET, K, R, tg_map, t_time, M_VERIFY, ETA, THETA_HIGH, THETA_LOW, pgrd_p, load_json(TC))
    save_json(res, 'result_b4.json')

if __name__ == '__main__':
    main()