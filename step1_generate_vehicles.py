import random
import csv

# ================== 核心参数（贴合文档规则） ==================
TOTAL_HOURS = 6                  # 6个小时段（0~5点）
VEHICLES_PER_HOUR = 150          # 每小时150辆 → 总计900辆
TOTAL_VEHICLES = TOTAL_HOURS * VEHICLES_PER_HOUR

REGIONS = list(range(6))         # 6个区域（0~5）
MIN_REGIONS = 2                  # 每车最少访问2个区域
MAX_REGIONS = 4                  # 每车最多访问4个区域

# 时间规则（文档要求：整点后0~600秒接入，停留60~300秒，行驶0~60秒）
FIRST_ENTER_MIN = 0              
FIRST_ENTER_MAX = 600
STAY_MIN = 60                    
STAY_MAX = 300
DRIVE_MIN = 0                    
DRIVE_MAX = 60

# 车辆属性规则
PRICE_MIN = 5.0
PRICE_MAX = 20.0
TRUST_RATE = 0.7                 # 70%可信


# ================== 生成单辆车轨迹 ==================
def generate_car(hour, car_seq):
    rows = []
    # 1. 随机选2~4个不同区域
    region_count = random.randint(MIN_REGIONS, MAX_REGIONS)
    regions = random.sample(REGIONS, region_count)
    
    # 2. 车辆固定属性（报价+可信度）
    price = round(random.uniform(PRICE_MIN, PRICE_MAX), 1)
    trusted = random.random() < TRUST_RATE
    
    # 3. 生成车辆ID（v{hour补两位}_{总序号补三位}）
    total_car_id = hour * VEHICLES_PER_HOUR + car_seq
    car_id_str = f"v{str(hour).zfill(2)}_{str(total_car_id).zfill(3)}"

    # 4. 计算首个区域进入时间（整点后0~600秒）
    hour_base_seconds = hour * 3600  # 整点对应的秒数（0点=0，1点=3600...）
    first_enter = random.randint(FIRST_ENTER_MIN, FIRST_ENTER_MAX)
    current_time = hour_base_seconds + first_enter
    
    # 5. 生成每个区域的轨迹数据
    for region_id in regions:
        start_time = current_time
        # 随机停留时间（60~300秒）
        stay_time = random.randint(STAY_MIN, STAY_MAX)
        end_time = start_time + stay_time
        
        # 追加轨迹行
        rows.append([
            car_id_str,
            region_id,
            start_time,
            end_time,
            price,
            trusted
        ])
        
        # 计算下一个区域进入时间（行驶时间0~60秒）
        drive_time = random.randint(DRIVE_MIN, DRIVE_MAX)
        current_time = end_time + drive_time
    
    return rows


# ================== 生成完整CSV文件（无任何验证） ==================
def generate_vehicles_csv(filename="step1_vehicles.csv"):
    all_data = []
    # 遍历6个小时，生成每小时150辆车
    for hour in range(TOTAL_HOURS):
        for car_seq in range(VEHICLES_PER_HOUR):
            car_data = generate_car(hour, car_seq)
            all_data.extend(car_data)
    
    # 只做一件事：写入CSV文件
    with open(filename, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        # 写入表头
        writer.writerow(["vehicle_id", "region_id", "start_time", "end_time", "cost", "is_trusted"])
        # 写入数据
        writer.writerows(all_data)
    
    # 只输出一句话，告知生成完成
    print(f"✅ 数据生成完成！文件已保存为：{filename}")


# ================== 运行生成 ==================
if __name__ == "__main__":
    generate_vehicles_csv()