import argparse
import os
import re
import shutil
import log
from tmdbv3api import TMDb, Search
from subprocess import call

from config import RMT_SUBEXT, get_config, RMT_MEDIAEXT, RMT_DISKFREESIZE, RMT_COUNTRY_EA, RMT_COUNTRY_AS, \
    RMT_MOVIETYPE
from functions import get_dir_files_by_ext, is_chinese, str_filesize, get_free_space_gb
from message.send import sendmsg


# 根据文件名转移对应字幕文件
def transfer_subtitles(in_path, org_name, new_name, mv_flag=False, rmt_mode="COPY"):
    file_list = get_dir_files_by_ext(in_path, RMT_SUBEXT)
    log.debug("【RMT】字幕文件清单：" + str(file_list))
    Media_FileNum = len(file_list)
    if Media_FileNum == 0:
        log.debug("【RMT】没有找到字幕文件")
    else:
        find_flag = False
        for file_item in file_list:
            org_subname = os.path.splitext(org_name)[0]
            if org_subname in file_item:
                find_flag = True
                file_ext = os.path.splitext(file_item)[-1]
                if file_item.find(".zh-cn" + file_ext) != -1:
                    new_file = os.path.splitext(new_name)[0] + ".zh-cn" + file_ext
                else:
                    new_file = os.path.splitext(new_name)[0] + file_ext
                if not os.path.exists(new_file):
                    if mv_flag:
                        log.debug("【RMT】正在移动字幕：" + file_item + " 到 " + new_file)
                        retcode = call(["mv", file_item, new_file])
                        if retcode == 0:
                            log.info("【RMT】字幕移动完成：" + new_file)
                        else:
                            log.error("【RMT】字幕移动失败，错误码：" + str(retcode))
                    else:
                        log.debug("【RMT】正在处理字幕：" + file_item + " 到 " + new_file)
                        if rmt_mode == "LINK":
                            rmt_mod_str = "硬链接"
                            retcode = call(["ln", file_item, new_file])
                        else:
                            rmt_mod_str = "复制"
                            retcode = call(["cp", file_item, new_file])
                        if retcode == 0:
                            log.info("【RMT】字幕" + rmt_mod_str + "完成：" + new_file)
                        else:
                            log.error("【RMT】字幕" + rmt_mod_str + "失败，错误码：" + str(retcode))
                else:
                    log.info("【RMT】字幕 " + new_file + "已存在！")
        if not find_flag:
            log.debug("【RMT】没有相同文件名的字幕文件，不处理！")


def transfer_bluray_dir(file_path, new_path, mv_flag=False, over_flag=False):
    config = get_config()
    if over_flag:
        log.warn("【RMT】正在删除已存在的目录：" + new_path)
        shutil.rmtree(new_path)
        log.warn("【RMT】" + new_path + " 已删除！")

    # 复制文件
    log.info("【RMT】正在复制目录：" + file_path + " 到 " + new_path)
    retcode = call(['cp -r', file_path, new_path])
    if retcode == 0:
        log.info("【RMT】文件复制完成：" + new_path)
    else:
        log.error("【RMT】文件复制失败，错误码：" + str(retcode))

    if mv_flag:
        if file_path != config['media'].get('movie_path') and file_path != config['media'].get('tv_path'):
            shutil.rmtree(file_path)
        log.info("【RMT】" + file_path + " 已删除！")


def transfer_files(file_path, file_item, new_file, mv_flag=False, over_flag=False, rmt_mode="COPY"):
    config = get_config()
    if over_flag:
        log.warn("【RMT】正在删除已存在的文件：" + new_file)
        os.remove(new_file)
        log.warn("【RMT】" + new_file + " 已删除！")

    # 复制文件
    log.info("【RMT】正在转移文件：" + file_item + " 到 " + new_file)
    if rmt_mode == "LINK":
        rmt_mod_str = "硬链接"
        retcode = call(['ln', file_item, new_file])
    else:
        rmt_mod_str = "复制"
        retcode = call(['cp', file_item, new_file])
    if retcode == 0:
        log.info("【RMT】文件" + rmt_mod_str + "完成：" + new_file)
    else:
        log.error("【RMT】文件" + rmt_mod_str + "失败，错误码：" + str(retcode))

    # 处理字幕
    transfer_subtitles(file_path, file_item, new_file, False, rmt_mode)

    if mv_flag:
        if file_path != config['media'].get('movie_path') and file_path != config['media'].get('tv_path'):
            shutil.rmtree(file_path)
        log.info("【RMT】" + file_path + " 已删除！")


# 转移一个目录下的所有文件
def transfer_directory(in_from, in_name, in_path, in_title=None, in_year=None, in_season=None, in_type=None,
                       mv_flag=False, noti_flag=True, target_dir=None):
    config = get_config()
    if in_from == "目录监控":
        rmt_mode = config['media'].get('sync_mod', 'COPY').upper()
    else:
        rmt_mode = config['pt'].get('rmt_mode', 'COPY').upper()
    if not in_name or not in_path:
        log.error("【RMT】输入参数错误!")
        return False
    # 遍历文件
    in_path = in_path.replace('\\\\', '/').replace('\\', '/')
    log.info("【RMT】开始处理：" + in_path)
    if not os.path.exists(in_path):
        log.error("【RMT】目录不存在：" + in_path)
        return False
    # 判断是不是原盘文件夹
    bluray_disk_flag = True if os.path.exists(os.path.join(in_path, "BDMV/index.bdmv")) else False
    file_list = get_dir_files_by_ext(in_path, RMT_MEDIAEXT)
    Media_FileNum = len(file_list)
    if bluray_disk_flag:
        in_type = "电影"
        log.info("【RMT】检测到蓝光原盘文件夹：" + in_path)
    else:
        log.debug("【RMT】文件清单：" + str(file_list))
        if Media_FileNum == 0:
            log.warn("【RMT】未找到支持的文件格式，下一次变化再处理...")
            return False

    # API检索出媒体信息
    media = get_media_info(in_path, in_name, in_type, in_year)
    if in_type:
        Search_Type = in_type
    else:
        Search_Type = media['search']
    Media_Type = media["type"]
    Media_Id = media["id"]
    if in_title:
        Media_Title = in_title
    else:
        Media_Title = media["name"]
    if in_year:
        Media_Year = in_year
    else:
        Media_Year = media["year"]
    Media_Pix = media['pix']
    Exist_FileNum = 0
    Media_FileSize = 0
    Backdrop_Path = ""
    if media["backdrop_path"]:
        Backdrop_Path = "https://image.tmdb.org/t/p/w500" + media["backdrop_path"]

    if Media_Id != "0":
        if Search_Type == "电影":
            # 检查剩余空间
            if target_dir:
                # 有输入target_dir时，往这个目录放
                movie_dist = target_dir
            else:
                movie_dist = config['media'].get('movie_path')
            disk_free_size = get_free_space_gb(movie_dist)
            if float(disk_free_size) < RMT_DISKFREESIZE:
                log.error("【RMT】目录" + movie_dist + "剩余磁盘空间不足" + RMT_DISKFREESIZE + "GB，不处理！")
                sendmsg("【RMT】磁盘空间不足", "目录" + movie_dist + "剩余磁盘空间不足" + RMT_DISKFREESIZE + "GB！")
                return False
            media_path = os.path.join(movie_dist, Media_Title + " (" + Media_Year + ")")
            # 未配置时默认进行分类
            movie_subtypedir = config['media'].get('movie_subtypedir', True)
            if movie_subtypedir:
                # 启用了电影分类
                exist_dir_flag = False
                # 在所有分类下查找是否有当前目录了
                for mtype in RMT_MOVIETYPE:
                    media_path = os.path.join(movie_dist, mtype, Media_Title + " (" + Media_Year + ")")
                    if os.path.exists(media_path):
                        # 该电影已在分类目录中存在
                        exist_dir_flag = True
                        break
                if not exist_dir_flag:
                    # 分类目录中未找到，则按媒体类型拼装新路径
                    media_path = os.path.join(movie_dist, Media_Type, Media_Title + " (" + Media_Year + ")")

            # 新路径是否存在
            trans_files_flag = False
            if not os.path.exists(media_path):
                # 不存在
                if bluray_disk_flag:
                    if rmt_mode == "LINK":
                        log.warn("【RMT】硬链接下不支持蓝光原盘目录，不处理...")
                    else:
                        subtype_dir = os.path.join(movie_dist, Media_Type)
                        if not os.path.exists(subtype_dir):
                            log.info("【RMT】正在创建目录：" + subtype_dir)
                            os.makedirs(subtype_dir)
                        transfer_bluray_dir(in_path, media_path)
                else:
                    # 不是蓝光则创新新目录
                    log.info("【RMT】正在创建目录：" + media_path)
                    os.makedirs(media_path)
                    trans_files_flag = True
            else:
                # 新路径存在
                if bluray_disk_flag:
                    log.warn("【RMT】蓝光原盘目录已存在：" + media_path)
                    return True
                else:
                    trans_files_flag = True

            # 开始判断和转移具体文件
            if trans_files_flag:
                for file_item in file_list:
                    Media_FileSize = Media_FileSize + os.path.getsize(file_item)
                    file_ext = os.path.splitext(file_item)[-1]
                    if Media_Pix != "":
                        if Media_Pix.upper() == "4K":
                            Media_Pix = "2160p"
                        new_file = os.path.join(media_path, Media_Title + " (" + Media_Year + ") - " + Media_Pix.lower() + file_ext)
                    else:
                        new_file = os.path.join(media_path, Media_Title + " (" + Media_Year + ")" + file_ext)
                    if not os.path.exists(new_file):
                        transfer_files(in_path, file_item, new_file, mv_flag, False, rmt_mode)
                    else:
                        if rmt_mode != "LINK":
                            ExistFile_Size = os.path.getsize(new_file)
                            if Media_FileSize > ExistFile_Size:
                                log.info("【RMT】文件" + new_file + "已存在，但新文件质量更好，覆盖...")
                                transfer_files(in_path, file_item, new_file, mv_flag, True, rmt_mode)
                            else:
                                Exist_FileNum = Exist_FileNum + 1
                                log.warn("【RMT】文件 " + new_file + "已存在，且质量更好！")
                        else:
                            log.debug("【RMT】文件 " + new_file + "已存在！")
            log.info("【RMT】" + in_name + " 转移完成！")
            msg_str = []
            if Media_Pix:
                msg_str.append("质量：" + str(Media_Pix).lower())
            if Media_FileSize:
                msg_str.append("大小：" + str_filesize(Media_FileSize))
            msg_str.append("来自：" + in_from)

            # 开始发送消息
            sendmsg_flag = True
            if Exist_FileNum != 0:
                save_note = str(Exist_FileNum) + " 个文件已存在！"
                msg_str.append("备注：" + save_note)
                # 有重复文件时，根据noti_flag来决定要不要发通知，避免信息干扰
                sendmsg_flag = noti_flag
            if sendmsg_flag:
                sendmsg("电影 " + Media_Title + " 转移完成", "\n".join(msg_str), Backdrop_Path)

        elif Search_Type == "电视剧":
            if bluray_disk_flag:
                log.error("【RMT】识别有误：蓝光原盘目录被识别为电视剧！")
                return False
            season_ary = []
            episode_ary = []

            # 检查剩余空间
            if target_dir:
                # 有输入target_dir时，往这个目录放
                tv_dist = target_dir
            else:
                tv_dist = config['media'].get('tv_path')

            disk_free_size = get_free_space_gb(tv_dist)
            if float(disk_free_size) < RMT_DISKFREESIZE:
                log.error("【RMT】目录" + tv_dist + "剩余磁盘空间不足" + RMT_DISKFREESIZE + "GB，不处理！")
                sendmsg("【RMT】磁盘空间不足", "目录" + tv_dist + "剩余磁盘空间不足" + RMT_DISKFREESIZE + "GB，不处理！")
                return False

            # 新路径
            media_path = os.path.join(tv_dist, Media_Title + " (" + Media_Year + ")")
            # 未配置时默认进行分类
            tv_subtypedir = config['media'].get('tv_subtypedir', True)
            if tv_subtypedir:
                media_path = os.path.join(tv_dist, Media_Type, Media_Title + " (" + Media_Year + ")")

            # 创建目录
            if not os.path.exists(media_path):
                log.info("【RMT】正在创建目录：" + media_path)
                os.makedirs(media_path)
            for file_item in file_list:
                Media_FileSize = Media_FileSize + os.path.getsize(file_item)
                file_ext = os.path.splitext(file_item)[-1]
                file_name = os.path.basename(file_item)
                # Sxx
                if in_season:
                    file_season = in_season
                else:
                    file_season = get_media_file_season(file_name)
                # Exx
                file_seq = get_media_file_seq(file_name)
                # 季 Season xx
                season_str = "Season " + str(int(file_season.replace("S", "")))
                if season_str not in season_ary:
                    season_ary.append(season_str)
                season_dir = os.path.join(media_path, season_str)
                # 集 xx
                file_seq_num = str(int(file_seq.replace("E", "").replace("P", "")))
                if file_seq_num not in episode_ary:
                    episode_ary.append(file_seq_num)
                # 创建目录
                if not os.path.exists(season_dir):
                    log.debug("【RMT】正在创建剧集目录：" + season_dir)
                    os.makedirs(season_dir)
                # 处理文件
                new_file = os.path.join(season_dir,
                                        Media_Title + " - " + file_season + file_seq + " - " + "第 "
                                        + file_seq_num + " 集" + file_ext)
                if not os.path.exists(new_file):
                    transfer_files(in_path, file_item, new_file, mv_flag, False, rmt_mode)
                else:
                    ExistFile_Size = os.path.getsize(new_file)
                    if rmt_mode != "LINK":
                        if Media_FileSize > ExistFile_Size:
                            log.info("【RMT】文件" + new_file + "已存在，但新文件质量更好，覆盖...")
                            transfer_files(in_path, file_item, new_file, mv_flag, True, rmt_mode)
                        else:
                            Exist_FileNum = Exist_FileNum + 1
                            log.warn("【RMT】文件 " + new_file + "已存在，且质量更好！")
                    else:
                        log.debug("【RMT】文件 " + new_file + "已存在！")
            log.info("【RMT】" + in_name + " 转移完成！")
            season_ary.sort()
            episode_ary.sort(key=int)

            # 开始发送消息
            msg_str = []
            if season_ary:
                msg_str.append("季：" + ', '.join(season_ary))
            if episode_ary:
                msg_str.append("集：" + ', '.join(episode_ary))
            if Media_FileNum:
                msg_str.append("文件数：" + str(Media_FileNum))
            if Media_FileSize:
                msg_str.append("总大小：" + str_filesize(Media_FileSize))
            msg_str.append("来自：" + in_from)
            sendmsg_flag = True
            if Exist_FileNum != 0:
                save_note = str(Exist_FileNum) + " 个文件已存在！"
                msg_str.append("备注：" + save_note)
                # 有重复文件时，根据noti_flag来决定要不要发通知，避免信息干扰
                sendmsg_flag = noti_flag
            if sendmsg_flag:
                sendmsg("电视剧 " + Media_Title + " 转移完成", "\n".join(msg_str), Backdrop_Path)
        else:
            log.error("【RMT】" + in_name + " 无法识别是什么类型的媒体文件！")
            sendmsg("【RMT】无法识别媒体类型！", "来源：" + in_from
                    + "\n种子名称：" + in_name)
            return False
    else:
        sendmsg("【RMT】媒体搜刮失败！", "来源：" + in_from
                + "\n种子名称：" + in_name
                + "\n识别标题：" + Media_Title
                + "\n识别类型：" + Search_Type)
        return False
    return True


def is_media_files_tv(in_path):
    flag = False
    tmp_list = get_dir_files_by_ext(in_path, RMT_MEDIAEXT)
    for tmp_file in tmp_list:
        tmp_name = os.path.basename(tmp_file)
        re_res = re.search(r"[\s\.]+[SE]P?\d{1,4}", tmp_name, re.IGNORECASE)
        if re_res:
            flag = True
            break
    if flag is False and len(tmp_list) > 2:
        # 目录下有多个附合后缀的文件，也认为是剧集
        flag = True
    return flag


# 获得媒体名称，用于API检索
def get_pt_media_name(in_name):
    out_name = in_name
    num_pos1 = num_pos2 = len(out_name)
    # 查找4位数字年份/分辨率的位置
    re_res1 = re.search(r"[\s\.]+\d{4}[\s\.]+", out_name)
    # 查找Sxx或Exx的位置
    re_res2 = re.search(r"[\s\.]+[SE]P?\d{1,4}", out_name, re.IGNORECASE)
    if re_res1:
        num_pos1 = re_res1.span()[0]
    if re_res2:
        num_pos2 = re_res2.span()[0]
    # 取三都最小
    num_pos = min(num_pos1, num_pos2, len(out_name))
    # 截取Year或Sxx或Exx前面的字符
    out_name = out_name[0:num_pos]
    if is_chinese(out_name):
        # 是否有空格，有就取前面的
        num_pos = out_name.find(' ')
        if num_pos != -1:
            out_name = out_name[0:num_pos]
        # 是否有点，有就取前面的
        num_pos = out_name.find('.')
        if num_pos != -1:
            out_name = out_name[0:num_pos]
        # 把中文中的英文、字符等全部去掉，数字要留下
        out_name = re.sub(r'[a-zA-Z【】\-\.\[\]\(\)\s]+', '', out_name, re.IGNORECASE).strip()
    else:
        # 不包括中文，则是英文名称
        out_name = out_name.replace(".", " ")
    return out_name


# 获得媒体文件的集数S00
def get_media_file_season(in_name):
    # 查找Sxx
    re_res = re.search(r"[\s\.]+(S\d{1,2})", in_name, re.IGNORECASE)
    if re_res:
        return re_res.group(1).upper()
    return "S01"


# 获得媒体文件的集数E00
def get_media_file_seq(in_name):
    # 查找Sxx
    re_res = re.search(r"[\s\.]+S?\d*(EP?\d{1,4})[\s\.]+", in_name, re.IGNORECASE)
    if re_res:
        ret_str = re_res.group(1).upper()
    else:
        # 可能数字就是全名，或者是第xx集
        ret_str = ""
        num_pos = in_name.find(".")
        if num_pos != -1:
            split_char = "."
        else:
            split_char = " "
        split_ary = in_name.split(split_char)
        for split_str in split_ary:
            split_str = split_str.replace("第", "").replace("集", "").strip()
            if split_str.isdigit() and (0 < int(split_str) < 1000):
                ret_str = "E" + split_str
                break
    if not ret_str:
        ret_str = ""
    return ret_str


# 获得媒体文件的分辨率
def get_media_file_pix(in_name):
    # 查找Sxx
    re_res = re.search(r"[\s\.]+[SUHD]*(\d{4}p)[\s\.]+", in_name, re.IGNORECASE)
    if re_res:
        return re_res.group(1).upper()
    else:
        re_res = re.search(r"[\s\.]+(\d+K)[\s\.]+", in_name, re.IGNORECASE)
        if re_res:
            return re_res.group(1).upper()
    return ""


# 获得媒体文件的Year
def get_media_file_year(in_name):
    # 查找Sxx
    re_res = re.search(r"[\s\.]+(\d{4})[\s\.]+", in_name, re.IGNORECASE)
    if re_res:
        return re_res.group(1).upper()
    return ""


# 搜刮媒体信息和类型
def get_media_info(in_path, in_name, in_type=None, in_year=None):
    # TheMovieDB
    tmdb = TMDb()
    config = get_config()
    rmt_tmdbkey = config['app'].get('rmt_tmdbkey')
    if not rmt_tmdbkey:
        # 兼容旧配置
        rmt_tmdbkey = config['pt'].get('rmt_tmdbkey')
    tmdb.api_key = rmt_tmdbkey
    if not tmdb.api_key:
        log.error("【RMT】rmt_tmdbkey未配置，无法搜刮媒体信息！")
    tmdb.language = 'zh'
    tmdb.debug = True

    info = {}
    media_id = "0"
    media_type = ""
    media_pix = ""
    backdrop_path = ""

    # 解析媒体名称
    media_name = get_pt_media_name(in_name)
    media_title = media_name

    # 解析媒体类型
    if in_type:
        if in_type == "电影":
            search_type = "电影"
        else:
            search_type = "电视剧"
    else:
        # 文件列表中有Sxx或者Exx的就是剧集，否则就是电影
        if is_media_files_tv(in_path):
            search_type = "电视剧"
        else:
            search_type = "电影"

    log.debug("【RMT】检索类型为：" + search_type)
    if not in_year:
        media_year = get_media_file_year(in_path)
    else:
        media_year = in_year
    log.debug("【RMT】识别年份为：" + str(media_year))

    if search_type == "电影":
        search = Search()
        log.info("【RMT】正在检索电影：" + media_name + '...')
        if media_year != "":
            movies = search.movies({"query": media_name, "year": media_year})
        else:
            movies = search.movies({"query": media_name})
        log.debug("【RMT】API返回：" + str(search.total_results))
        if len(movies) == 0:
            log.error("【RMT】未找到媒体信息!")
        else:
            info = movies[0]
            for movie in movies:
                if movie.title == media_name or movie.release_date[0:4] == media_year:
                    # 优先使用名称或者年份完全匹配的，匹配不到则取第一个
                    info = movie
                    break
            media_id = info.id
            media_title = info.title
            log.info(">电影ID：" + str(info.id) + "，上映日期：" + info.release_date + "，电影名称：" + info.title)
            media_year = info.release_date[0:4]
            backdrop_path = info.backdrop_path
            if media_type == "":
                # 国家
                media_language = info.original_language
                if 'zh' in media_language:
                    media_type = "华语电影"
                else:
                    media_type = "外语电影"
        # 解析分辨率
        media_pix = get_media_file_pix(in_path)

    else:
        search = Search()
        log.info("【RMT】正在检索剧集：" + media_name + '...')
        if media_year != "":
            tvs = search.tv_shows({"query": media_name, "year": media_year})
        else:
            tvs = search.tv_shows({"query": media_name})
        log.debug("【RMT】API返回：" + str(search.total_results))
        if len(tvs) == 0:
            log.error("【RMT】未找到媒体信息!")
            info = {}
        else:
            info = tvs[0]
            for tv in tvs:
                if tv.name == media_name or tv.first_air_date[0:4] == media_year:
                    # 优先使用名称或者年份完全匹配的，匹配不到则取第一个
                    info = tv
                    break
            media_id = info.id
            media_title = info.name
            log.info(">剧集ID：" + str(info.id) + "，剧集名称：" + info.name + "，上映日期：" + info.first_air_date)
            media_year = info.first_air_date[0:4]
            backdrop_path = info.backdrop_path
            if media_type == "":
                # 类型 动漫、纪录片、儿童、综艺
                media_genre_ids = info.genre_ids
                if 16 in media_genre_ids:
                    # 动漫
                    media_type = "动漫"
                elif 99 in media_genre_ids:
                    # 纪录片
                    media_type = "纪录片"
                elif 10762 in media_genre_ids:
                    # 儿童
                    media_type = "儿童"
                elif 10764 in media_genre_ids or 10767 in media_genre_ids:
                    # 综艺
                    media_type = "综艺"
                else:
                    # 国家
                    media_country = info.origin_country
                    if 'CN' in media_country:
                        media_type = "国产剧"
                    elif set(RMT_COUNTRY_EA).intersection(set(media_country)):
                        media_type = "欧美剧"
                    elif set(RMT_COUNTRY_AS).intersection(set(media_country)):
                        media_type = "日韩剧"
                    else:
                        media_type = "国产剧"
    log.debug("【RMT】剧集类型：" + media_type)
    return {"search": search_type, "type": media_type, "id": media_id, "name": media_title, "year": media_year,
            "info": info, "pix": media_pix, "backdrop_path": backdrop_path}


# 全量转移
def transfer_all(pt_path=None):
    if not pt_path:
        return
    if not os.path.exists(pt_path):
        print("【RMT】目录不存在：" + pt_path)
        return
    config = get_config()
    print("【RMT】正在转移以下目录中的全量文件：" + pt_path)
    print("【RMT】转移模式为：" + config['pt'].get('rmt_mode'))
    for f_dir in os.listdir(pt_path):
        file_path = os.path.join(pt_path, f_dir)
        file_name = os.path.basename(file_path)
        print("【RMT】开始处理：" + file_path)
        try:
            transfer_directory(in_from="PT", in_name=file_name, in_path=file_path)
            print("【RMT】处理完成：" + file_path)
        except Exception as err:
            print("【RMT】发生错误：" + str(err))
    print("【RMT】" + pt_path + " 处理完成！")


if __name__ == "__main__":
    # 参数
    parser = argparse.ArgumentParser(description='Rename Media Tool')
    parser.add_argument('-c', '--config', dest='config_file', required=True, help='Config File Path')
    parser.add_argument('-d', '--dir', dest='pt_path', required=True, help='Media Files Saved Path')
    args = parser.parse_args()
    print("【RMT】配置文件地址：" + args.config_file)
    print("【RMT】处理路径：" + args.pt_path)
    os.environ['NASTOOL_CONFIG'] = args.config_file
    transfer_all(args.pt_path)
