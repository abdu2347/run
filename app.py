import math
import random
from flask import Flask, render_template, request, send_file, jsonify
from datetime import datetime, timedelta
import xml.etree.ElementTree as ET
import zipfile
import io
import calendar

app = Flask(__name__)

# 首页路由，加载前端页面
@app.route('/')
def index():
    return render_template('index.html')

def generate_tcx(start_time):
    # ============= 核心参数：总时间严格锁定14-18分钟（840-1080秒） =============
    total_seconds = random.randint(840, 1080)  # 固定14-18分钟
    single_lap_distance = 400.0               # 标准400米跑道
    total_laps = round(random.uniform(5.2, 6.0), 2)  # 5.2-6圈，总距离2080-2400米
    total_distance = round(total_laps * single_lap_distance, 2)

    # 每圈配速随机波动（模拟真实跑步体力变化）
    lap_time_list = []
    remaining_seconds = total_seconds
    int_laps = int(total_laps)
    for i in range(int_laps):
        if i == int_laps - 1:
            lap_t = remaining_seconds  # 最后一圈分配剩余时间，保证总时间准确
        else:
            lap_t = random.randint(135, 185)  # 单圈时间135-185秒，贴合真人配速
        lap_time_list.append(lap_t)
        remaining_seconds -= lap_t
    # 处理小数圈时间
    fractional_lap = total_laps - int_laps
    if fractional_lap > 0:
        total_seconds = sum(lap_time_list) + lap_time_list[-1] * fractional_lap

    # ============= 跑道基础参数 =============
    points_per_lap = 120  # 每圈120个轨迹点，保证轨迹平滑
    n_points = int(points_per_lap * total_laps)
    straight_length = 100.0  # 直道100米
    curve_length = 100.0     # 弯道100米
    radius_meters = curve_length / math.pi  # 弯道半径

    # 江苏师大西操场基准经纬度（可自行修改）
    base_center_lat = 34.197550
    base_center_lon = 117.173188

    # 米转经纬度换算因子（GPS坐标计算核心）
    meter_to_deg_lat = 1 / 111111.0
    meter_to_deg_lon = 1 / (111111.0 * math.cos(math.radians(base_center_lat)))

    # ============= 核心优化1：每圈轨迹彻底不重叠（独立大偏移） =============
    lap_offsets = []  # 每圈独立的中心偏移量，提前生成
    for lap_idx in range(int(math.ceil(total_laps))):
        # 每圈偏移1.0~2.0米，彻底错开轨迹，且不偏离跑道
        lap_lat_off = random.uniform(-2.0, 2.0) * meter_to_deg_lat
        lap_lon_off = random.uniform(-2.0, 2.0) * meter_to_deg_lon
        lap_offsets.append((lap_lat_off, lap_lon_off))

    # ============= 核心优化2：临时变道参数（模拟避让前方行人） =============
    # 随机选择1-2个圈数进行变道，贴合真实跑步不会频繁变道
    change_lap_list = random.sample(range(int(math.ceil(total_laps))), k=random.randint(1, 2))
    change_distance = 0.6  # 变道距离0.6米（真人跑步变道的合理宽度）
    # 变道仅在**直道段**发生（弯道不会变道，符合真人跑步习惯）
    change_segments = ["straight1", "straight2"]  # 西侧直道、东侧直道

    # ============= 其他参数：GPS噪声、心率 =============
    point_noise_meter = 0.2  # 每个轨迹点的GPS微小抖动，模拟定位误差
    points_hr = []  # 心率数据（75-130次/分，非线性波动，贴合真实跑步）
    for i in range(n_points + 1):
        x = i / n_points if n_points > 0 else 0
        hr = 75 + int(45 * (1 - math.cos(x * math.pi))) + random.randint(-5, 5)
        points_hr.append(max(75, min(130, hr)))

    # ============= 构建TCX标准文件结构（Garmin官方格式，保证APP能识别） =============
    root = ET.Element(
        "TrainingCenterDatabase",
        xmlns="http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2",
        **{"xmlns:xsi": "http://www.w3.org/2001/XMLSchema-instance",
           "xsi:schemaLocation": "http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2 http://www.garmin.com/xmlschemas/TrainingCenterDatabasev2.xsd"}
    )
    activities = ET.SubElement(root, "Activities")
    activity = ET.SubElement(activities, "Activity", Sport="Running")
    ET.SubElement(activity, "Id").text = start_time.isoformat()

    lap = ET.SubElement(activity, "Lap", StartTime=start_time.isoformat())
    ET.SubElement(lap, "TotalTimeSeconds").text = str(round(total_seconds, 2))
    ET.SubElement(lap, "DistanceMeters").text = str(total_distance)
    ET.SubElement(lap, "Intensity").text = "Active"
    ET.SubElement(lap, "TriggerMethod").text = "Manual"
    track = ET.SubElement(lap, "Track")

    dt = total_seconds / n_points if n_points > 0 else 1.0  # 每个轨迹点的时间间隔

    # 跑道四段划分：西侧直道→北侧弯道→东侧直道→南侧弯道
    s1_end = straight_length  # 西侧直道结束（0-100米）
    c1_end = straight_length + curve_length  # 北侧弯道结束（100-200米）
    s2_end = straight_length + curve_length + straight_length  # 东侧直道结束（200-300米）
    c2_end = single_lap_distance  # 南侧弯道结束（300-400米）

    # ============= 生成轨迹点（核心：每圈偏移+直道变道+GPS噪声） =============
    for i in range(n_points + 1):
        # 计算当前总距离、当前时间、当前圈的相对距离
        current_total_dist = total_distance * i / n_points if i < n_points else total_distance
        current_time = start_time + timedelta(seconds=dt * i)
        current_lap_dist = current_total_dist % single_lap_distance
        if math.isclose(current_lap_dist, 0.0) and current_total_dist > 0:
            current_lap_dist = c2_end

        # 确定当前是第几圈、获取当前圈的基础偏移
        current_lap_idx = int(current_total_dist / single_lap_distance)
        lap_lat_off, lap_lon_off = lap_offsets[min(current_lap_idx, len(lap_offsets) - 1)]
        # 计算当前圈的跑道中心坐标（基础偏移后）
        center_lat = base_center_lat + lap_lat_off
        center_lon = base_center_lon + lap_lon_off

        # 计算当前圈的跑道关键点坐标（直道/弯道的分界点）
        lon_rad_off = radius_meters * meter_to_deg_lon
        lat_half_straight = (straight_length / 2.0) * meter_to_deg_lat
        north_curve_lat = center_lat + lat_half_straight  # 北侧弯道中心纬度
        south_curve_lat = center_lat - lat_half_straight  # 南侧弯道中心纬度
        start_lat = south_curve_lat  # 每圈起点纬度
        start_lon = center_lon - lon_rad_off  # 每圈起点经度

        # 初始化当前轨迹点坐标
        lat, lon = 0.0, 0.0
        # 标记当前是否在直道段、是否需要变道
        is_change_lap = current_lap_idx in change_lap_list  # 当前圈是否需要变道
        current_segment = ""  # 当前所在跑道段（straight1/straight2/curve1/curve2）

        # ============= 分段计算GPS坐标 + 临时变道逻辑 =============
        if 0 <= current_lap_dist < s1_end:
            # 1. 西侧直道（向北跑）- 可变道
            current_segment = "straight1"
            progress = current_lap_dist / straight_length
            lat = start_lat + progress * (north_curve_lat - south_curve_lat)
            lon = start_lon
            # 变道：向西侧偏移（避让前方行人），仅直道中段触发（20-80米）
            if is_change_lap and current_segment in change_segments and 20 < current_lap_dist < 80:
                lon -= change_distance * meter_to_deg_lon

        elif s1_end <= current_lap_dist < c1_end:
            # 2. 北侧弯道（向东跑）- 不变道
            current_segment = "curve1"
            dist_on_curve = current_lap_dist - s1_end
            angle_rad = (dist_on_curve / curve_length) * math.pi
            current_angle = math.pi - angle_rad
            lat = north_curve_lat + (radius_meters * meter_to_deg_lat) * math.sin(current_angle)
            lon = center_lon + (radius_meters * meter_to_deg_lon) * math.cos(current_angle)

        elif c1_end <= current_lap_dist < s2_end:
            # 3. 东侧直道（向南跑）- 可变道
            current_segment = "straight2"
            dist_on_straight = current_lap_dist - c1_end
            progress = dist_on_straight / straight_length
            lat = north_curve_lat - progress * (north_curve_lat - south_curve_lat)
            lon = center_lon + lon_rad_off
            # 变道：向东侧偏移（避让前方行人），仅直道中段触发（220-280米）
            if is_change_lap and current_segment in change_segments and 220 < current_lap_dist < 280:
                lon += change_distance * meter_to_deg_lon

        elif s2_end <= current_lap_dist <= c2_end:
            # 4. 南侧弯道（向西跑）- 不变道
            current_segment = "curve2"
            dist_on_curve = current_lap_dist - s2_end
            dist_on_curve = max(0.0, min(dist_on_curve, curve_length))
            angle_rad = (dist_on_curve / curve_length) * math.pi
            current_angle = 2 * math.pi - angle_rad
            lat = south_curve_lat + (radius_meters * meter_to_deg_lat) * math.sin(current_angle)
            lon = center_lon + (radius_meters * meter_to_deg_lon) * math.cos(current_angle)
            # 圈末回到起点，保证轨迹闭合
            if math.isclose(current_lap_dist, c2_end):
                lat, lon = start_lat, start_lon

        # ============= 最终优化：添加GPS微小噪声，让轨迹更真实 =============
        lat += random.uniform(-point_noise_meter, point_noise_meter) * meter_to_deg_lat
        lon += random.uniform(-point_noise_meter, point_noise_meter) * meter_to_deg_lon

        # ============= 写入TCX轨迹点数据（包含坐标、距离、心率） =============
        trackpoint = ET.SubElement(track, "Trackpoint")
        ET.SubElement(trackpoint, "Time").text = current_time.isoformat()
        # 位置坐标
        position = ET.SubElement(trackpoint, "Position")
        ET.SubElement(position, "LatitudeDegrees").text = f"{lat:.8f}"
        ET.SubElement(position, "LongitudeDegrees").text = f"{lon:.8f}"
        # 累计距离
        ET.SubElement(trackpoint, "DistanceMeters").text = f"{current_total_dist:.2f}"
        # 心率
        hr_elem = ET.SubElement(trackpoint, "HeartRateBpm")
        ET.SubElement(hr_elem, "Value").text = str(points_hr[i])

    return ET.ElementTree(root)

# ============= 生成TCX文件接口（完全匹配前端JSON传参，无报错） =============
@app.route('/generate', methods=['POST'])
def generate():
    try:
        # 接收前端传递的JSON时间数据
        data = request.get_json()
        if not data or 'times' not in data or len(data['times']) == 0:
            return jsonify({'error': '请至少选择一个跑步时间！'}), 400

        start_times = []
        # 解析并验证时间（年、月、日、时、分、秒独立参数，与前端一致）
        for time_item in data['times']:
            year = int(time_item.get('year', 0))
            month = int(time_item.get('month', 0))
            day = int(time_item.get('day', 0))
            hour = int(time_item.get('hour', 0))
            minute = int(time_item.get('minute', 0))
            second = int(time_item.get('second', 0))

            # 时间合法性验证
            if not (2000 <= year <= 2100):
                return jsonify({'error': f'年份{year}无效，需在2000-2100之间'}), 400
            if not (1 <= month <= 12):
                return jsonify({'error': f'月份{month}无效，需在1-12之间'}), 400
            last_day = calendar.monthrange(year, month)[1]
            if not (1 <= day <= last_day):
                return jsonify({'error': f'{year}年{month}月只有{last_day}天，日期{day}无效'}), 400
            if not (0 <= hour <= 23 and 0 <= minute <= 59 and 0 <= second <= 59):
                return jsonify({'error': '时/分/秒无效，需在合法范围'}), 400

            start_times.append(datetime(year, month, day, hour, minute, second))

        # 单个时间：生成独立TCX文件下载
        if len(start_times) == 1:
            st = start_times[0]
            tree = generate_tcx(st)
            output = io.BytesIO()
            tree.write(output, encoding='UTF-8', xml_declaration=True)
            output.seek(0)
            return send_file(
                output,
                mimetype='application/xml',
                as_attachment=True,
                download_name=f"run_{st.strftime('%Y%m%d_%H%M%S')}.tcx"
            )
        # 多个时间：打包成ZIP文件下载
        else:
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
                for st in start_times:
                    tree = generate_tcx(st)
                    output = io.BytesIO()
                    tree.write(output, encoding='UTF-8', xml_declaration=True)
                    output.seek(0)
                    zf.writestr(f"run_{st.strftime('%Y%m%d_%H%M%S')}.tcx", output.getvalue())
            zip_buffer.seek(0)
            return send_file(
                zip_buffer,
                mimetype='application/zip',
                as_attachment=True,
                download_name='runs.zip'
            )

    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': f'生成文件失败：{str(e)}'}), 500

# ============= 程序启动入口（直接py app.py即可运行，无需额外命令） =============
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
