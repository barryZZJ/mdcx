import os
import re
import shutil
import traceback

import aiofiles
import aiofiles.os

from mdcx.config.manager import config
from mdcx.consts import IS_MAC, IS_WINDOWS
from mdcx.models.base.file import _deal_path_name, get_cd_part
from mdcx.models.core.utils import render_name_template
from mdcx.models.enums import FileMode
from mdcx.models.flags import Flags
from mdcx.models.log_buffer import LogBuffer
from mdcx.models.types import (
    CreateFolderContext,
    DealOldFilesInput,
    FileInfo,
    GenerateFileNameInput,
    GetFolderPathInput,
    GetOutPutNameInput,
    MoveMovieContext,
)
from mdcx.number import get_file_number, get_number_letters, is_uncensored
from mdcx.signals import signal
from mdcx.utils import convert_path, nfd2c, split_path
from mdcx.utils.file import copy_file_async, delete_file_async, move_file_async, read_link_async
from mdcx.utils.path import showFilePath


async def creat_folder(
    json_data: CreateFolderContext,
    folder_new_path: str,
    file_path: str,
    file_new_path: str,
    thumb_new_path_with_filename: str,
    poster_new_path_with_filename: str,
) -> bool:
    """判断是否创建文件夹，目标文件是否有重复文件。file_new_path是最终路径"""

    json_data["dont_move_movie"] = False  # 不需要移动和重命名视频
    json_data["del_file_path"] = False  # 在 move movie 时需要删除自己，自己是软链接，目标是原始文件
    dont_creat_folder = False  # 不需要创建文件夹

    # 正常模式、视频模式时，软连接关，成功后不移动文件开时，这时不创建文件夹
    if config.main_mode < 3 and config.soft_link == 0 and not config.success_file_move:
        dont_creat_folder = True

    # 更新模式、读取模式，选择更新c文件时，不创建文件夹
    if config.main_mode > 2 and config.update_mode == "c":
        dont_creat_folder = True

    # 如果不需要创建文件夹，当不重命名时，直接返回
    if dont_creat_folder:
        if not config.success_file_rename:
            json_data["dont_move_movie"] = True
            return True

    # 如果不存在目标文件夹，则创建文件夹

    elif not await aiofiles.os.path.isdir(folder_new_path):
        try:
            await aiofiles.os.makedirs(folder_new_path)
            LogBuffer.log().write("\n 🍀 Folder done! (new)")
            return True
        except Exception as e:
            if not await aiofiles.os.path.exists(folder_new_path):
                LogBuffer.log().write(f"\n 🔴 Failed to create folder! \n    {str(e)}")
                if len(folder_new_path) > 250:
                    LogBuffer.log().write("\n    可能是目录名过长！！！建议限制目录名长度！！！越小越好！！！")
                    LogBuffer.error().write("创建文件夹失败！可能是目录名过长！")
                else:
                    LogBuffer.log().write("\n    请检查是否有写入权限！")
                    LogBuffer.error().write("创建文件夹失败！请检查是否有写入权限！")
                return False

    # 判断是否有重复文件（Windows、Mac大小写不敏感）
    convert_file_path = convert_path(file_path).lower()
    convert_file_new_path = convert_path(file_new_path).lower()

    # 当目标文件存在，是软链接时
    if await aiofiles.os.path.islink(file_new_path):
        # 路径相同，是自己
        if convert_file_path == convert_file_new_path:
            json_data["dont_move_movie"] = True
        # 路径不同，删掉目标文件即可（不验证是否真实路径了，太麻烦）
        else:
            # 在移动时删除即可。delete_file(file_new_path)
            # 创建软链接前需要删除目标路径文件
            pass
        return True

    # 当目标文件存在，不是软链接时
    elif await aiofiles.os.path.exists(file_new_path):
        # 待刮削的文件不是软链接
        if not await aiofiles.os.path.islink(file_path):
            # 如果路径相同，则代表已经在成功文件夹里，不是重复文件（大小写不敏感）
            if convert_file_path == convert_file_new_path:
                json_data["dont_move_movie"] = True
                if await aiofiles.os.path.exists(thumb_new_path_with_filename):
                    json_data["thumb_path"] = thumb_new_path_with_filename
                if await aiofiles.os.path.exists(poster_new_path_with_filename):
                    json_data["poster_path"] = poster_new_path_with_filename
                return True

            # 路径不同
            else:
                try:
                    # 当都指向同一个文件时(此处路径不能用小写，因为Linux大小写敏感)
                    if (await aiofiles.os.stat(file_path)).st_ino == (await aiofiles.os.stat(file_new_path)).st_ino:
                        # 硬链接开时，不需要处理
                        # 除非 scrape_success_folder_and_skip_link 为 True，此时视为关闭软硬链接
                        if config.soft_link == 2 and not config.scrape_success_folder_and_skip_link:
                            json_data["dont_move_movie"] = True
                        # 非硬链接模式，删除目标文件
                        else:
                            # 在移动时删除即可。delete_file(file_new_path)
                            pass
                        return True
                except Exception:
                    pass
                # TODO 命名没有带分集
                #  Success folder already exists a same name file!
                #  ❗️ Current file: J:\simon\test-out\4K-DSVR-0817\4K-DSVR-0817-cd4.mp4
                #  ❗️ Success folder already exists file: J:\simon\test-out\4K-DSVR-0817\4K-DSVR-0817.mp4
                # 路径不同，当指向不同文件时
                json_data["title"] = "Success folder already exists a same name file!"
                LogBuffer.error().write(
                    f"Success folder already exists a same name file! \n ❗️ Current file: {file_path} \n ❗️ Success folder already exists file: {file_new_path} "
                )
                return False

        # 待刮削文件是软链接
        else:
            # 看待刮削文件真实路径，路径相同，是同一个文件
            real_file_path = await read_link_async(file_path)
            if convert_path(real_file_path).lower() == convert_file_new_path:
                # 非软硬链接时，标记删除待刮削文件自身
                if config.soft_link == 0:
                    json_data["del_file_path"] = True
                # 软硬链接时，标记不处理
                else:
                    json_data["dont_move_movie"] = True
                return True
            # 路径不同，是两个文件
            else:
                json_data["title"] = "Success folder already exists a same name file!"
                LogBuffer.error().write(
                    f"Success folder already exists a same name file! \n"
                    f" ❗️ Current file is symlink file: {file_path} \n"
                    f" ❗️ real file: {real_file_path} \n"
                    f" ❗️ Success folder already exists another real file: {file_new_path} "
                )
                return False

    # 目标文件不存在时
    return True


async def move_movie(json_data: MoveMovieContext, file_path: str, file_new_path: str) -> bool:
    # 明确不需要移动的，直接返回
    if json_data["dont_move_movie"]:
        LogBuffer.log().write(f"\n 🍀 Movie done! \n 🙉 [Movie] {file_path}")
        return True

    # 明确要删除自己的，删除后返回
    if json_data["del_file_path"]:
        await delete_file_async(file_path)
        LogBuffer.log().write(f"\n 🍀 Movie done! \n 🙉 [Movie] {file_new_path}")
        json_data["file_path"] = file_new_path
        return True

    # scrape_success_folder_and_skip_link 为 True 时，不应额外创建软硬链接，当前文件不论是否软硬链接，视为普通文件直接移动
    # 软链接模式开时，先删除目标文件，再创建软链接(需考虑自身是软链接的情况)
    if config.soft_link == 1 and not config.scrape_success_folder_and_skip_link:
        temp_path = file_path
        # 自身是软链接时，获取真实路径
        if await aiofiles.os.path.islink(file_path):
            file_path = await read_link_async(file_path)  # delete_file(temp_path)
        # 删除目标路径存在的文件，否则会创建失败，
        await delete_file_async(file_new_path)
        try:
            await aiofiles.os.symlink(file_path, file_new_path)
            json_data["file_path"] = file_new_path
            LogBuffer.log().write(
                f"\n 🍀 Softlink done! \n    Softlink file: {file_new_path} \n    Source file: {file_path}"
            )
            return True
        except Exception as e:
            if IS_WINDOWS:
                LogBuffer.log().write(
                    "\n 🥺 Softlink failed! (创建软连接失败！"
                    "注意：Windows 平台输出目录必须是本地磁盘！不支持挂载的 NAS 盘或网盘！"
                    f"如果是本地磁盘，请尝试以管理员身份运行！)\n{str(e)}\n 🙉 [Movie] {temp_path}"
                )
            else:
                LogBuffer.log().write(f"\n 🥺 Softlink failed! (创建软连接失败！)\n{str(e)}\n 🙉 [Movie] {temp_path}")
            signal.show_traceback_log(traceback.format_exc())
            signal.show_log_text(traceback.format_exc())
            return False

    # 硬链接模式开时，创建硬链接
    elif config.soft_link == 2 and not config.scrape_success_folder_and_skip_link:
        try:
            await delete_file_async(file_new_path)
            await aiofiles.os.link(file_path, file_new_path)
            json_data["file_path"] = file_new_path
            LogBuffer.log().write(
                f"\n 🍀 HardLink done! \n    HadrLink file: {file_new_path} \n    Source file: {file_path}"
            )
            return True
        except Exception as e:
            if IS_MAC:
                LogBuffer.log().write(
                    "\n 🥺 HardLink failed! (创建硬连接失败！"
                    "注意：硬链接要求待刮削文件和输出目录必须是同盘，不支持跨卷！"
                    "如要跨卷可以尝试软链接模式！另外，Mac 平台非本地磁盘不支持创建硬链接（权限问题），"
                    f"请选择软链接模式！)\n{str(e)} "
                )
            else:
                LogBuffer.log().write(
                    f"\n 🥺 HardLink failed! (创建硬连接失败！注意："
                    f"硬链接要求待刮削文件和输出目录必须是同盘，不支持跨卷！"
                    f"如要跨卷可以尝试软链接模式！)\n{str(e)} "
                )
            LogBuffer.error().write("创建硬连接失败！")
            signal.show_traceback_log(traceback.format_exc())
            signal.show_log_text(traceback.format_exc())
            return False

    # 其他情况，就移动文件
    result, error_info = await move_file_async(file_path, file_new_path)
    if result:
        LogBuffer.log().write(f"\n 🍀 Movie done! \n 🙉 [Movie] {file_new_path}")
        if await aiofiles.os.path.islink(file_new_path):
            LogBuffer.log().write(
                f"\n    It's a symlink file! Source file: \n    {await read_link_async(file_new_path)}"  # win 不能用os.path.realpath()，返回的结果不准
            )
        json_data["file_path"] = file_new_path
        return True
    else:
        if "are the same file" in error_info.lower():  # 大小写不同，win10 用raidrive 挂载 google drive 改名会出错
            if json_data["cd_part"]:
                temp_folder, temp_file = split_path(file_new_path)
                if temp_file not in await aiofiles.os.listdir(temp_folder):
                    await move_file_async(file_path, file_new_path + ".MDCx.tmp")
                    await move_file_async(file_new_path + ".MDCx.tmp", file_new_path)
            LogBuffer.log().write(f"\n 🍀 Movie done! \n 🙉 [Movie] {file_new_path}")
            json_data["file_path"] = file_new_path
            return True
        LogBuffer.log().write(f"\n 🔴 Failed to move movie file to success folder!\n    {error_info}")
        return False


def _get_folder_path(file_path: str, success_folder: str, json_data: GetFolderPathInput) -> tuple[str, str]:
    folder_name: str = config.folder_name.replace("\\", "/")  # 设置-命名-视频目录名
    folder_path, file_name = split_path(file_path)  # 当前文件的目录和文件名

    # 更新模式 或 读取模式
    if config.main_mode == 3 or config.main_mode == 4:
        if config.update_mode == "c":
            folder_name = split_path(folder_path)[1]
            json_data["folder_name"] = folder_name
            return folder_path, folder_name
        elif "bc" in config.update_mode:
            folder_name = config.update_b_folder
            success_folder = split_path(folder_path)[0]
            if "a" in config.update_mode:
                success_folder = split_path(success_folder)[0]
                folder_name = os.path.join(config.update_a_folder, config.update_b_folder).replace("\\", "/").strip("/")
        elif config.update_mode == "d":
            folder_name = config.update_d_folder
            success_folder = split_path(file_path)[0]

    # 正常模式 或 整理模式
    else:
        # 关闭软连接，并且成功后移动文件关时，使用原来文件夹
        if config.soft_link == 0 and not config.success_file_move:
            folder_path = split_path(file_path)[0]
            json_data["folder_name"] = folder_name
            return folder_path, folder_name

    # 当根据刮削模式得到的视频目录名为空时，使用成功输出目录
    if not folder_name:
        json_data["folder_name"] = ""
        return success_folder, folder_name

    show_4k = "folder" in config.show_4k
    show_cnword = config.folder_cnword
    show_moword = "folder" in config.show_moword
    should_escape_result = True
    folder_new_name, folder_name, number, originaltitle, outline, title = render_name_template(
        folder_name, file_path, json_data, show_4k, show_cnword, show_moword, should_escape_result
    )

    # 去除各种乱七八糟字符后，文件夹名为空时，使用number显示
    folder_name_temp = re.sub(r'[\\/:*?"<>|\r\n]+', "", folder_new_name)
    folder_name_temp = folder_name_temp.replace("//", "/").replace("--", "-").strip("-")
    if not folder_name_temp:
        folder_new_name = number

    # 判断文件夹名长度，超出长度时，截短标题名
    folder_name_max = int(config.folder_name_max)
    if len(folder_new_name) > folder_name_max:
        cut_index = folder_name_max - len(folder_new_name)
        if "originaltitle" in folder_name:
            LogBuffer.log().write(
                f"\n 💡 当前目录名长度：{len(folder_new_name)}，最大允许长度：{folder_name_max}，目录命名时将去除原标题后{abs(cut_index)}个字符!"
            )
            folder_new_name = folder_new_name.replace(originaltitle, originaltitle[0:cut_index])
        elif "title" in folder_name:
            LogBuffer.log().write(
                f"\n 💡 当前目录名长度：{len(folder_new_name)}，最大允许长度：{folder_name_max}，目录命名时将去除标题后{abs(cut_index)}个字符!"
            )
            folder_new_name = folder_new_name.replace(title, title[0:cut_index])
        elif "outline" in folder_name:
            LogBuffer.log().write(
                f"\n 💡 当前目录名长度：{len(folder_new_name)}，最大允许长度：{folder_name_max}，目录命名时将去除简介后{abs(cut_index)}个字符!"
            )
            folder_new_name = folder_new_name.replace(outline, outline[0:cut_index])

    # 替换一些字符
    folder_new_name = folder_new_name.replace("--", "-").strip("-").strip("- .")

    # 用在保存文件时的名字，需要过滤window异常字符 特殊字符
    folder_new_name = re.sub(r'[\\:*?"<>|\r\n]+', "", folder_new_name).strip(" /")

    # 过滤文件夹名字前后的空格
    folder_new_name = folder_new_name.replace(" /", "/").replace(" \\", "\\").replace("/ ", "/").replace("\\ ", "\\")

    # 日文浊音转换（mac的坑,osx10.12以下使用nfd）
    folder_new_name = nfd2c(folder_new_name)

    # 生成文件夹名
    folder_new_path = os.path.join(success_folder, folder_new_name)
    folder_new_path = convert_path(folder_new_path)
    folder_new_path = nfd2c(folder_new_path)

    json_data["folder_name"] = folder_new_name

    return folder_new_path.strip().replace(" /", "/"), folder_name


def _generate_file_name(file_path: str, json_data: GenerateFileNameInput, folder_name_template: str) -> str:
    file_full_name = split_path(file_path)[1]
    file_name, file_ex = os.path.splitext(file_full_name)

    # 如果成功后不重命名，则返回原来名字
    if not config.success_file_rename:
        return file_name

    # 更新模式 或 读取模式
    if config.main_mode == 3 or config.main_mode == 4:
        file_name_template = config.update_c_filetemplate
    # 正常模式 或 整理模式
    else:
        file_name_template = config.naming_file

    # 获取文件信息
    cd_part = json_data["cd_part"]

    show_4k = "file" in config.show_4k
    show_cnword = config.file_cnword
    show_moword = "file" in config.show_moword
    should_escape_result = True
    file_name, file_name_template, number, originaltitle, outline, title = render_name_template(
        file_name_template, file_path, json_data, show_4k, show_cnword, show_moword, should_escape_result
    )

    # 当“视频文件名”和“视频目录名”相同，且没有设置防屏蔽字符时，视为想要分集命名，
    # 此时直接修改文件名开头为目录名，避免因为长度限制处理导致文件名开头与目录名不一致的问题。
    # 注意应该放在_render_name_template处理后，保证folder_name_template和file_name_template就算被处理也相同。
    if folder_name_template == file_name_template and not config.prevent_char:
        file_name = json_data["folder_name"]
        file_name += cd_part
        return file_name

    file_name += cd_part

    # 去除各种乱七八糟字符后，文件名为空时，使用number显示
    file_name_temp = re.sub(r'[\\/:*?"<>|\r\n]+', "", file_name)
    file_name_temp = file_name_temp.replace("//", "/").replace("--", "-").strip("-")
    if not file_name_temp:
        file_name = number

    # 插入防屏蔽字符（115）
    prevent_char = config.prevent_char
    if prevent_char:
        file_char_list = list(file_name)
        file_name = prevent_char.join(file_char_list)

    # 判断文件名长度，超出长度时，截短文件名
    file_name_max = int(config.file_name_max)
    if len(file_name) > file_name_max:
        cut_index = file_name_max - len(file_name) - len(file_ex)

        # 如果没有防屏蔽字符，截短标题或者简介，这样不影响其他字段阅读
        if not prevent_char:
            if "originaltitle" in file_name_template:
                LogBuffer.log().write(
                    f"\n 💡 当前文件名长度：{len(file_name)}，"
                    f"最大允许长度：{file_name_max}，文件命名时将去除原标题后{abs(cut_index)}个字符!"
                )
                file_name = file_name.replace(originaltitle, originaltitle[:cut_index])
            elif "title" in file_name_template:
                LogBuffer.log().write(
                    f"\n 💡 当前文件名长度：{len(file_name)}，"
                    f"最大允许长度：{file_name_max}，文件命名时将去除标题后{abs(cut_index)}个字符!"
                )
                file_name = file_name.replace(title, title[:cut_index])
            elif "outline" in file_name_template:
                LogBuffer.log().write(
                    f"\n 💡 当前文件名长度：{len(file_name)}，"
                    f"最大允许长度：{file_name_max}，文件命名时将去除简介后{abs(cut_index)}个字符!"
                )
                file_name = file_name.replace(outline, outline[:cut_index])

        # 加了防屏蔽字符，直接截短
        else:
            file_name = file_name[:cut_index]

    # 替换一些字符
    file_name = file_name.replace("//", "/").replace("--", "-").strip("-")

    # 用在保存文件时的名字，需要过滤window异常字符 特殊字符
    file_name = re.sub(r'[\\/:*?"<>|\r\n]+', "", file_name).strip()

    # 过滤文件名字前后的空格
    file_name = file_name.replace(" /", "/").replace(" \\", "\\").replace("/ ", "/").replace("\\ ", "\\").strip()

    # 日文浊音转换（mac的坑,osx10.12以下使用nfd）
    file_name = nfd2c(file_name)

    return file_name


def get_output_name(
    json_data: GetOutPutNameInput, file_path: str, success_folder: str, file_ex: str
) -> tuple[str, str, str, str, str, str, str, str, str, str]:
    # =====================================================================================更新输出文件夹名
    folder_new_path, foldername_template = _get_folder_path(file_path, success_folder, json_data)
    folder_new_path = _deal_path_name(folder_new_path)
    # =====================================================================================更新实体文件命名规则
    naming_rule = _generate_file_name(file_path, json_data, foldername_template)
    naming_rule = _deal_path_name(naming_rule)
    # =====================================================================================生成文件和nfo新路径
    file_new_name = naming_rule + file_ex.lower()
    nfo_new_name = naming_rule + ".nfo"
    file_new_path = convert_path(os.path.join(folder_new_path, file_new_name))
    nfo_new_path = convert_path(os.path.join(folder_new_path, nfo_new_name))
    # =====================================================================================生成图片下载路径
    poster_new_name = naming_rule + "-poster.jpg"
    thumb_new_name = naming_rule + "-thumb.jpg"
    fanart_new_name = naming_rule + "-fanart.jpg"
    poster_new_path_with_filename = convert_path(os.path.join(folder_new_path, poster_new_name))
    thumb_new_path_with_filename = convert_path(os.path.join(folder_new_path, thumb_new_name))
    fanart_new_path_with_filename = convert_path(os.path.join(folder_new_path, fanart_new_name))
    # =====================================================================================生成图片最终路径
    # 如果图片命名规则不加文件名并且视频目录不为空
    if config.pic_simple_name and json_data["folder_name"].replace(" ", ""):
        poster_final_name = "poster.jpg"
        thumb_final_name = "thumb.jpg"
        fanart_final_name = "fanart.jpg"
    else:
        poster_final_name = naming_rule + "-poster.jpg"
        thumb_final_name = naming_rule + "-thumb.jpg"
        fanart_final_name = naming_rule + "-fanart.jpg"
    poster_final_path = convert_path(os.path.join(folder_new_path, poster_final_name))
    thumb_final_path = convert_path(os.path.join(folder_new_path, thumb_final_name))
    fanart_final_path = convert_path(os.path.join(folder_new_path, fanart_final_name))

    return (
        folder_new_path,
        file_new_path,
        nfo_new_path,
        poster_new_path_with_filename,
        thumb_new_path_with_filename,
        fanart_new_path_with_filename,
        naming_rule,
        poster_final_path,
        thumb_final_path,
        fanart_final_path,
    )


async def get_file_info_v2(file_path: str, copy_sub: bool = True) -> FileInfo:
    optional_data = {}
    movie_number = ""
    has_sub = False
    c_word = ""
    cd_part = ""
    destroyed = ""
    leak = ""
    wuma = ""
    youma = ""
    mosaic = ""
    sub_list = []
    cnword_style = config.cnword_style
    if Flags.file_mode == FileMode.Again and file_path in Flags.new_again_dic:
        temp_number, temp_url, temp_website = Flags.new_again_dic[file_path]
        if temp_number:  # 如果指定了番号，则使用指定番号
            movie_number = temp_number
            optional_data["appoint_number"] = temp_number
        if temp_url:
            optional_data["appoint_url"] = temp_url
            optional_data["website_name"] = temp_website
    elif Flags.file_mode == FileMode.Single:  # 刮削单文件（工具页面）
        optional_data["appoint_url"] = Flags.appoint_url

    # 获取显示路径
    file_path = file_path.replace("\\", "/")
    file_show_path = showFilePath(file_path)

    # 获取文件名
    folder_path, file_full_name = split_path(file_path)  # 获取去掉文件名的路径、完整文件名（含扩展名）
    file_name, file_ex = os.path.splitext(file_full_name)  # 获取文件名（不含扩展名）、扩展名(含有.)
    file_name_temp = file_name + "."
    nfo_old_name = file_name + ".nfo"
    nfo_old_path = os.path.join(folder_path, nfo_old_name)
    file_show_name = file_name

    # 软链接时，获取原身路径(用来查询原身文件目录是否有字幕)
    file_ori_path_no_ex = ""
    if await aiofiles.os.path.islink(file_path):
        file_ori_path = await read_link_async(file_path)
        file_ori_path_no_ex = os.path.splitext(file_ori_path)[0]

    try:
        # 清除防屏蔽字符
        prevent_char = config.prevent_char
        if prevent_char:
            file_path = file_path.replace(prevent_char, "")
            file_name = file_name.replace(prevent_char, "")

        # 获取番号
        if not movie_number:
            movie_number = get_file_number(file_path, config.escape_string_list)

        # 259LUXU-1111, 非mgstage、avsex去除前面的数字前缀
        temp_n = re.findall(r"\d{3,}([a-zA-Z]+-\d+)", movie_number)
        optional_data["short_number"] = temp_n[0] if temp_n else ""

        cd_char = config.cd_char
        cd_part = await get_cd_part(file_name, movie_number, cd_char)

        # 判断是否是马赛克破坏版
        umr_style = str(config.umr_style)
        if (
            "-uncensored." in file_path.lower()
            or "umr." in file_path.lower()
            or "破解" in file_path
            or "克破" in file_path
            or (umr_style and umr_style in file_path)
            or "-u." in file_path.lower()
            or "-uc." in file_path.lower()
        ):
            destroyed = umr_style
            mosaic = "无码破解"

        # 判断是否国产
        if not mosaic:
            if "国产" in file_path or "麻豆" in file_path or "國產" in file_path:
                mosaic = "国产"
            else:
                md_list = [
                    "国产",
                    "國產",
                    "麻豆",
                    "传媒",
                    "傳媒",
                    "皇家华人",
                    "皇家華人",
                    "精东",
                    "精東",
                    "猫爪影像",
                    "貓爪影像",
                    "91CM",
                    "91MS",
                    "导演系列",
                    "導演系列",
                    "MDWP",
                    "MMZ",
                    "MLT",
                    "MSM",
                    "LAA",
                    "MXJ",
                    "SWAG",
                ]
                for each in md_list:
                    if each in file_path:
                        mosaic = "国产"

        # 判断是否流出
        leak_style = str(config.leak_style)
        if not mosaic:
            if "流出" in file_path or "leaked" in file_path.lower() or (leak_style and leak_style in file_path):
                leak = leak_style
                mosaic = "无码流出"

        # 判断是否无码
        wuma_style = str(config.wuma_style)
        if not mosaic:
            if (
                "无码" in file_path
                or "無碼" in file_path
                or "無修正" in file_path
                or "uncensored" in file_path.lower()
                or is_uncensored(movie_number)
            ):
                wuma = wuma_style
                mosaic = "无码"

        # 判断是否有码
        youma_style = str(config.youma_style)
        if not mosaic:
            if "有码" in file_path or "有碼" in file_path:
                youma = youma_style
                mosaic = "有码"

        # 查找本地字幕文件
        cnword_list = config.cnword_char.replace("，", ",").split(",")
        if "-C." in str(cnword_list).upper():
            cnword_list.append("-C ")
        sub_type_list = config.sub_type.split("|")  # 本地字幕后缀
        for sub_type in sub_type_list:  # 查找本地字幕, 可能多个
            sub_type_chs = ".chs" + sub_type
            sub_path_chs = os.path.join(folder_path, (file_name + sub_type_chs))
            sub_path = os.path.join(folder_path, (file_name + sub_type))
            if await aiofiles.os.path.exists(sub_path_chs):
                sub_list.append(sub_type_chs)
                c_word = cnword_style  # 中文字幕影片后缀
                has_sub = True
            if await aiofiles.os.path.exists(sub_path):
                sub_list.append(sub_type)
                c_word = cnword_style  # 中文字幕影片后缀
                has_sub = True
            if file_ori_path_no_ex:  # 原身路径
                sub_path2 = file_ori_path_no_ex + sub_type
                if await aiofiles.os.path.exists(sub_path2):
                    c_word = cnword_style  # 中文字幕影片后缀
                    has_sub = True

        # 判断路径名是否有中文字幕字符
        if not has_sub:
            cnword_list.append("-uc.")
            file_name_temp = file_name_temp.upper().replace("CD", "").replace("CARIB", "")  # 去掉cd/carib，避免-c误判
            if "letter" in cd_char and "endc" in cd_char:
                file_name_temp = re.sub(r"(-|\d{2,}|\.)C\.$", ".", file_name_temp)

            for each in cnword_list:
                if each.upper() in file_name_temp:
                    if "無字幕" not in file_path and "无字幕" not in file_path:
                        c_word = cnword_style  # 中文字幕影片后缀
                        has_sub = True
                        break

        # 判断nfo中是否有中文字幕、马赛克
        if (not has_sub or not mosaic) and await aiofiles.os.path.exists(nfo_old_path):
            try:
                async with aiofiles.open(nfo_old_path, encoding="utf-8") as f:
                    nfo_content = await f.read()
                if not has_sub:
                    if ">中文字幕</" in nfo_content:
                        c_word = cnword_style  # 中文字幕影片后缀
                        has_sub = True
                if not mosaic:
                    if ">无码流出</" in nfo_content or ">無碼流出</" in nfo_content:
                        leak = leak_style
                        mosaic = "无码流出"
                    elif ">无码破解</" in nfo_content or ">無碼破解</" in nfo_content:
                        destroyed = umr_style
                        mosaic = "无码破解"
                    elif ">无码</" in nfo_content or ">無碼</" in nfo_content:
                        wuma = wuma_style
                        mosaic = "无码"
                    elif ">有碼</" in nfo_content or ">有碼</" in nfo_content:
                        youma = youma_style
                        mosaic = "有码"
                    elif ">国产</" in nfo_content or ">國產</" in nfo_content:
                        youma = youma_style
                        mosaic = "国产"
                    elif ">里番</" in nfo_content or ">裏番</" in nfo_content:
                        youma = youma_style
                        mosaic = "里番"
                    elif ">动漫</" in nfo_content or ">動漫</" in nfo_content:
                        youma = youma_style
                        mosaic = "动漫"
            except Exception:
                signal.show_traceback_log(traceback.format_exc())

        if not has_sub and await aiofiles.os.path.exists(nfo_old_path):
            try:
                async with aiofiles.open(nfo_old_path, encoding="utf-8") as f:
                    nfo_content = await f.read()
                if "<genre>中文字幕</genre>" in nfo_content or "<tag>中文字幕</tag>" in nfo_content:
                    c_word = cnword_style  # 中文字幕影片后缀
                    has_sub = True
            except Exception:
                signal.show_traceback_log(traceback.format_exc())

        # 查找字幕包目录字幕文件
        subtitle_add = config.subtitle_add
        if not has_sub and copy_sub and subtitle_add:
            subtitle_folder = config.subtitle_folder
            subtitle_add = config.subtitle_add
            if subtitle_add and subtitle_folder:  # 复制字幕开
                for sub_type in sub_type_list:
                    sub_path_1 = os.path.join(subtitle_folder, (movie_number + cd_part + sub_type))
                    sub_path_2 = os.path.join(subtitle_folder, file_name + sub_type)
                    sub_path_list = [sub_path_1, sub_path_2]
                    sub_file_name = file_name + sub_type
                    if config.subtitle_add_chs:
                        sub_file_name = file_name + ".chs" + sub_type
                        sub_type = ".chs" + sub_type
                    sub_new_path = os.path.join(folder_path, sub_file_name)
                    for sub_path in sub_path_list:
                        if await aiofiles.os.path.exists(sub_path):
                            await copy_file_async(sub_path, sub_new_path)
                            LogBuffer.log().write(f"\n\n 🍉 Sub file '{sub_file_name}' copied successfully! ")
                            sub_list.append(sub_type)
                            c_word = cnword_style  # 中文字幕影片后缀
                            has_sub = True
                            break

        file_show_name = movie_number
        suffix_sort_list = config.suffix_sort.split(",")
        for each in suffix_sort_list:
            if each == "moword":
                file_show_name += destroyed + leak + wuma + youma
            elif each == "cnword":
                file_show_name += c_word
        file_show_name += cd_part

    except Exception:
        signal.show_traceback_log(file_path)
        signal.show_traceback_log(traceback.format_exc())
        signal.show_log_text(traceback.format_exc())
        LogBuffer.log().write("\n" + file_path)
        LogBuffer.log().write("\n" + traceback.format_exc())

    return FileInfo(
        number=movie_number,
        letters=get_number_letters(movie_number),
        has_sub=has_sub,
        c_word=c_word,
        cd_part=cd_part,
        destroyed=destroyed,
        leak=leak,
        wuma=wuma,
        youma=youma,
        mosaic=mosaic,
        file_path=convert_path(file_path),
        folder_path=folder_path,
        file_name=file_name,
        file_ex=file_ex,
        sub_list=sub_list,
        file_show_name=file_show_name,
        file_show_path=file_show_path,
        short_number=optional_data.get("short_number", ""),
        appoint_number=optional_data.get("appoint_number", ""),
        appoint_url=optional_data.get("appoint_url", ""),
        website_name=optional_data.get("website_name", ""),
    )


async def deal_old_files(
    json_data: DealOldFilesInput,
    folder_old_path: str,
    folder_new_path: str,
    file_path: str,
    file_new_path: str,
    thumb_new_path_with_filename: str,
    poster_new_path_with_filename: str,
    fanart_new_path_with_filename: str,
    nfo_new_path: str,
    file_ex: str,
    poster_final_path: str,
    thumb_final_path: str,
    fanart_final_path: str,
) -> tuple[bool, bool]:
    """
    处理本地已存在的thumb、poster、fanart、nfo
    """
    # 转换文件路径
    file_path = convert_path(file_path)
    nfo_old_path = file_path.replace(file_ex, ".nfo")
    nfo_new_path = convert_path(nfo_new_path)
    folder_old_path = convert_path(folder_old_path)
    folder_new_path = convert_path(folder_new_path)
    extrafanart_old_path = convert_path(os.path.join(folder_old_path, "extrafanart"))
    extrafanart_new_path = convert_path(os.path.join(folder_new_path, "extrafanart"))
    extrafanart_folder = config.extrafanart_folder
    extrafanart_copy_old_path = convert_path(os.path.join(folder_old_path, extrafanart_folder))
    extrafanart_copy_new_path = convert_path(os.path.join(folder_new_path, extrafanart_folder))
    trailer_name = config.trailer_simple_name
    trailer_old_folder_path = convert_path(os.path.join(folder_old_path, "trailers"))
    trailer_new_folder_path = convert_path(os.path.join(folder_new_path, "trailers"))
    trailer_old_file_path = convert_path(os.path.join(trailer_old_folder_path, "trailer.mp4"))
    trailer_new_file_path = convert_path(os.path.join(trailer_new_folder_path, "trailer.mp4"))
    trailer_old_file_path_with_filename = convert_path(nfo_old_path.replace(".nfo", "-trailer.mp4"))
    trailer_new_file_path_with_filename = convert_path(nfo_new_path.replace(".nfo", "-trailer.mp4"))
    theme_videos_old_path = convert_path(os.path.join(folder_old_path, "backdrops"))
    theme_videos_new_path = convert_path(os.path.join(folder_new_path, "backdrops"))
    extrafanart_extra_old_path = convert_path(os.path.join(folder_old_path, "behind the scenes"))
    extrafanart_extra_new_path = convert_path(os.path.join(folder_new_path, "behind the scenes"))

    # 图片旧路径转换路径
    poster_old_path_with_filename = file_path.replace(file_ex, "-poster.jpg")
    thumb_old_path_with_filename = file_path.replace(file_ex, "-thumb.jpg")
    fanart_old_path_with_filename = file_path.replace(file_ex, "-fanart.jpg")
    poster_old_path_no_filename = convert_path(os.path.join(folder_old_path, "poster.jpg"))
    thumb_old_path_no_filename = convert_path(os.path.join(folder_old_path, "thumb.jpg"))
    fanart_old_path_no_filename = convert_path(os.path.join(folder_old_path, "fanart.jpg"))
    file_path_list = {
        nfo_old_path,
        nfo_new_path,
        thumb_old_path_with_filename,
        thumb_old_path_no_filename,
        thumb_new_path_with_filename,
        thumb_final_path,
        poster_old_path_with_filename,
        poster_old_path_no_filename,
        poster_new_path_with_filename,
        poster_final_path,
        fanart_old_path_with_filename,
        fanart_old_path_no_filename,
        fanart_new_path_with_filename,
        fanart_final_path,
        trailer_old_file_path_with_filename,
        trailer_new_file_path_with_filename,
    }
    folder_path_list = {
        extrafanart_old_path,
        extrafanart_new_path,
        extrafanart_copy_old_path,
        extrafanart_copy_new_path,
        trailer_old_folder_path,
        trailer_new_folder_path,
        theme_videos_old_path,
        theme_videos_new_path,
        extrafanart_extra_old_path,
        extrafanart_extra_new_path,
    }

    # 视频模式进行清理
    main_mode = config.main_mode
    if main_mode == 2 and "sort_del" in config.switch_on:
        for each in file_path_list:
            if await aiofiles.os.path.exists(each):
                await delete_file_async(each)
        for each in folder_path_list:
            if await aiofiles.os.path.isdir(each):
                shutil.rmtree(each, ignore_errors=True)
        return False, False

    # 非视频模式，将本地已有的图片、剧照等文件，按照命名规则，重新命名和移动。这个环节仅应用设置-命名设置，没有应用设置-下载的设置
    # 抢占图片的处理权
    single_folder_catched = False  # 剧照、剧照副本、主题视频 这些单文件夹的处理权，他们只需要处理一次
    pic_final_catched = False  # 最终图片（poster、thumb、fanart）的处理权
    if thumb_new_path_with_filename not in Flags.pic_catch_set:
        if thumb_final_path != thumb_new_path_with_filename:
            if thumb_final_path not in Flags.pic_catch_set:  # 不带文件名的图片的下载权利（下载权利只给它一个）
                Flags.pic_catch_set.add(thumb_final_path)
                pic_final_catched = True
        else:
            pic_final_catched = True  # 带文件名的图片，下载权利给每一个。（如果有一个下载好了，未下载的可以直接复制）
    # 处理 extrafanart、extrafanart副本、主题视频、附加视频
    if pic_final_catched and extrafanart_new_path not in Flags.extrafanart_deal_set:
        Flags.extrafanart_deal_set.add(extrafanart_new_path)
        single_folder_catched = True
    """
    需要考虑旧文件分集情况（带文件名、不带文件名）、旧文件不同扩展名情况，他们如何清理或保留
    需要考虑新文件分集情况（带文件名、不带文件名）
    需要考虑分集同时刮削如何节省流量
    需要考虑分集带文件名图片是否会有重复水印问题
    """

    # poster_marked True 不加水印，避免二次加水印,；poster_exists 是不是存在本地图片
    json_data["poster_marked"] = True
    json_data["thumb_marked"] = True
    json_data["fanart_marked"] = True
    poster_exists = True
    thumb_exists = True
    fanart_exists = True
    trailer_exists = True

    # 软硬链接模式，不处理旧的图片
    # 除非 scrape_success_folder_and_skip_link 为 True，此时视为关闭软硬链接
    if config.soft_link != 0 and not config.scrape_success_folder_and_skip_link:
        return pic_final_catched, single_folder_catched

    """
    保留图片或删除图片说明：
    图片保留的前提条件：非整理模式，并且满足（在保留名单 或 读取模式 或 图片已下载）。此时不清理 poster.jpg thumb.jpg fanart.jpg（在del_noname_pic中清理）。
    图片保留的命名方式：保留时会保留为最终路径 和 文件名-thumb.jpg (thumb 需要复制一份为 文件名-thumb.jpg，避免 poster 没有，要用 thumb 裁剪，或者 fanart 要复制 thumb)
    图片下载的命名方式：新下载的则都保存为 文件名-thumb.jpg（因为多分集同时下载为 thumb.jpg 时会冲突）
    图片下载的下载条件：如果最终路径有内容，则不下载。如果 文件名-thumb.jpg 有内容，也不下载。
    图片下载的复制条件：如果不存在 文件名-thumb.jpg，但是存在 thumb.jpg，则复制 thumb.jpg 为 文件名-thumb.jpg
    最终的图片处理：在最终的 rename pic 环节，如果最终路径有内容，则删除非最终路径的内容；如果最终路径没内容，表示图片是刚下载的，要改成最终路径。
    """

    # poster 处理：寻找对应文件放到最终路径上。这样避免刮削失败时，旧的图片被删除
    done_poster_path = Flags.file_done_dic.get(json_data["number"], {}).get("poster")
    done_poster_path_copy = True
    try:
        # 图片最终路径等于已下载路径时，图片是已下载的，不需要处理
        if (
            done_poster_path
            and await aiofiles.os.path.exists(done_poster_path)
            and split_path(done_poster_path)[0] == split_path(poster_final_path)[0]
        ):  # 如果存在已下载完成的文件，尝试复制
            done_poster_path_copy = False  # 标记未复制！此处不复制，在poster download中复制
        elif await aiofiles.os.path.exists(poster_final_path):
            pass  # windows、mac大小写不敏感，暂不解决
        elif poster_new_path_with_filename != poster_final_path and await aiofiles.os.path.exists(
            poster_new_path_with_filename
        ):
            await move_file_async(poster_new_path_with_filename, poster_final_path)
        elif poster_old_path_with_filename != poster_final_path and await aiofiles.os.path.exists(
            poster_old_path_with_filename
        ):
            await move_file_async(poster_old_path_with_filename, poster_final_path)
        elif poster_old_path_no_filename != poster_final_path and await aiofiles.os.path.exists(
            poster_old_path_no_filename
        ):
            await move_file_async(poster_old_path_no_filename, poster_final_path)
        else:
            poster_exists = False

        if poster_exists:
            Flags.file_done_dic[json_data["number"]].update({"local_poster": poster_final_path})
            # 清理旧图片
            if poster_old_path_with_filename.lower() != poster_final_path.lower() and await aiofiles.os.path.exists(
                poster_old_path_with_filename
            ):
                await delete_file_async(poster_old_path_with_filename)
            if poster_old_path_no_filename.lower() != poster_final_path.lower() and await aiofiles.os.path.exists(
                poster_old_path_no_filename
            ):
                await delete_file_async(poster_old_path_no_filename)
            if poster_new_path_with_filename.lower() != poster_final_path.lower() and await aiofiles.os.path.exists(
                poster_new_path_with_filename
            ):
                await delete_file_async(poster_new_path_with_filename)
        elif Flags.file_done_dic[json_data["number"]]["local_poster"]:
            await copy_file_async(Flags.file_done_dic[json_data["number"]]["local_poster"], poster_final_path)

    except Exception:
        signal.show_log_text(traceback.format_exc())

    # thumb 处理：寻找对应文件放到最终路径上。这样避免刮削失败时，旧的图片被删除
    done_thumb_path = Flags.file_done_dic.get(json_data["number"], {}).get("thumb")
    done_thumb_path_copy = True
    try:
        # 图片最终路径等于已下载路径时，图片是已下载的，不需要处理
        if (
            done_thumb_path
            and await aiofiles.os.path.exists(done_thumb_path)
            and split_path(done_thumb_path)[0] == split_path(thumb_final_path)[0]
        ):
            done_thumb_path_copy = False  # 标记未复制！此处不复制，在 thumb download中复制
        elif await aiofiles.os.path.exists(thumb_final_path):
            pass
        elif thumb_new_path_with_filename != thumb_final_path and await aiofiles.os.path.exists(
            thumb_new_path_with_filename
        ):
            await move_file_async(thumb_new_path_with_filename, thumb_final_path)
        elif thumb_old_path_with_filename != thumb_final_path and await aiofiles.os.path.exists(
            thumb_old_path_with_filename
        ):
            await move_file_async(thumb_old_path_with_filename, thumb_final_path)
        elif thumb_old_path_no_filename != thumb_final_path and await aiofiles.os.path.exists(
            thumb_old_path_no_filename
        ):
            await move_file_async(thumb_old_path_no_filename, thumb_final_path)
        else:
            thumb_exists = False

        if thumb_exists:
            Flags.file_done_dic[json_data["number"]].update({"local_thumb": thumb_final_path})
            # 清理旧图片
            if thumb_old_path_with_filename.lower() != thumb_final_path.lower() and await aiofiles.os.path.exists(
                thumb_old_path_with_filename
            ):
                await delete_file_async(thumb_old_path_with_filename)
            if thumb_old_path_no_filename.lower() != thumb_final_path.lower() and await aiofiles.os.path.exists(
                thumb_old_path_no_filename
            ):
                await delete_file_async(thumb_old_path_no_filename)
            if thumb_new_path_with_filename.lower() != thumb_final_path.lower() and await aiofiles.os.path.exists(
                thumb_new_path_with_filename
            ):
                await delete_file_async(thumb_new_path_with_filename)
        elif Flags.file_done_dic[json_data["number"]]["local_thumb"]:
            await copy_file_async(Flags.file_done_dic[json_data["number"]]["local_thumb"], thumb_final_path)

    except Exception:
        signal.show_log_text(traceback.format_exc())

    # fanart 处理：寻找对应文件放到最终路径上。这样避免刮削失败时，旧的图片被删除
    done_fanart_path = Flags.file_done_dic.get(json_data["number"], {}).get("fanart")
    done_fanart_path_copy = True
    try:
        # 图片最终路径等于已下载路径时，图片是已下载的，不需要处理
        if (
            done_fanart_path
            and await aiofiles.os.path.exists(done_fanart_path)
            and split_path(done_fanart_path)[0] == split_path(fanart_final_path)[0]
        ):
            done_fanart_path_copy = False  # 标记未复制！此处不复制，在 fanart download中复制
        elif await aiofiles.os.path.exists(fanart_final_path):
            pass
        elif fanart_new_path_with_filename != fanart_final_path and await aiofiles.os.path.exists(
            fanart_new_path_with_filename
        ):
            await move_file_async(fanart_new_path_with_filename, fanart_final_path)
        elif fanart_old_path_with_filename != fanart_final_path and await aiofiles.os.path.exists(
            fanart_old_path_with_filename
        ):
            await move_file_async(fanart_old_path_with_filename, fanart_final_path)
        elif fanart_old_path_no_filename != fanart_final_path and await aiofiles.os.path.exists(
            fanart_old_path_no_filename
        ):
            await move_file_async(fanart_old_path_no_filename, fanart_final_path)
        else:
            fanart_exists = False

        if fanart_exists:
            Flags.file_done_dic[json_data["number"]].update({"local_fanart": fanart_final_path})
            # 清理旧图片
            if fanart_old_path_with_filename.lower() != fanart_final_path.lower() and await aiofiles.os.path.exists(
                fanart_old_path_with_filename
            ):
                await delete_file_async(fanart_old_path_with_filename)
            if fanart_old_path_no_filename.lower() != fanart_final_path.lower() and await aiofiles.os.path.exists(
                fanart_old_path_no_filename
            ):
                await delete_file_async(fanart_old_path_no_filename)
            if fanart_new_path_with_filename.lower() != fanart_final_path.lower() and await aiofiles.os.path.exists(
                fanart_new_path_with_filename
            ):
                await delete_file_async(fanart_new_path_with_filename)
        elif Flags.file_done_dic[json_data["number"]]["local_fanart"]:
            await copy_file_async(Flags.file_done_dic[json_data["number"]]["local_fanart"], fanart_final_path)

    except Exception:
        signal.show_log_text(traceback.format_exc())

    # 更新图片地址
    json_data["poster_path"] = poster_final_path if poster_exists and done_poster_path_copy else ""
    json_data["thumb_path"] = thumb_final_path if thumb_exists and done_thumb_path_copy else ""
    json_data["fanart_path"] = fanart_final_path if fanart_exists and done_fanart_path_copy else ""

    # nfo 处理
    try:
        if await aiofiles.os.path.exists(nfo_new_path):
            if nfo_old_path.lower() != nfo_new_path.lower() and await aiofiles.os.path.exists(nfo_old_path):
                await delete_file_async(nfo_old_path)
        elif nfo_old_path != nfo_new_path and await aiofiles.os.path.exists(nfo_old_path):
            await move_file_async(nfo_old_path, nfo_new_path)
    except Exception:
        signal.show_log_text(traceback.format_exc())

    # trailer
    if trailer_name:  # 预告片名字不含视频文件名
        # trailer最终路径等于已下载路径时，trailer是已下载的，不需要处理
        if await aiofiles.os.path.exists(trailer_new_file_path):
            if await aiofiles.os.path.exists(trailer_old_file_path_with_filename):
                await delete_file_async(trailer_old_file_path_with_filename)
            elif await aiofiles.os.path.exists(trailer_new_file_path_with_filename):
                await delete_file_async(trailer_new_file_path_with_filename)
        elif trailer_old_file_path != trailer_new_file_path and await aiofiles.os.path.exists(trailer_old_file_path):
            if not await aiofiles.os.path.exists(trailer_new_folder_path):
                await aiofiles.os.makedirs(trailer_new_folder_path)
            await move_file_async(trailer_old_file_path, trailer_new_file_path)
        elif await aiofiles.os.path.exists(trailer_new_file_path_with_filename):
            if not await aiofiles.os.path.exists(trailer_new_folder_path):
                await aiofiles.os.makedirs(trailer_new_folder_path)
            await move_file_async(trailer_new_file_path_with_filename, trailer_new_file_path)
        elif await aiofiles.os.path.exists(trailer_old_file_path_with_filename):
            if not await aiofiles.os.path.exists(trailer_new_folder_path):
                await aiofiles.os.makedirs(trailer_new_folder_path)
            await move_file_async(trailer_old_file_path_with_filename, trailer_new_file_path)

        # 删除旧文件夹，用不到了
        if trailer_old_folder_path != trailer_new_folder_path and await aiofiles.os.path.exists(
            trailer_old_folder_path
        ):
            shutil.rmtree(trailer_old_folder_path, ignore_errors=True)
        # 删除带文件名文件，用不到了
        if await aiofiles.os.path.exists(trailer_old_file_path_with_filename):
            await delete_file_async(trailer_old_file_path_with_filename)
        if trailer_new_file_path_with_filename != trailer_old_file_path_with_filename and await aiofiles.os.path.exists(
            trailer_new_file_path_with_filename
        ):
            await delete_file_async(trailer_new_file_path_with_filename)
    else:
        # 目标文件带文件名
        if await aiofiles.os.path.exists(trailer_new_file_path_with_filename):
            if (
                trailer_old_file_path_with_filename != trailer_new_file_path_with_filename
                and await aiofiles.os.path.exists(trailer_old_file_path_with_filename)
            ):
                await delete_file_async(trailer_old_file_path_with_filename)
        elif (
            trailer_old_file_path_with_filename != trailer_new_file_path_with_filename
            and await aiofiles.os.path.exists(trailer_old_file_path_with_filename)
        ):
            await move_file_async(trailer_old_file_path_with_filename, trailer_new_file_path_with_filename)
        elif await aiofiles.os.path.exists(trailer_old_file_path):
            await move_file_async(trailer_old_file_path, trailer_new_file_path_with_filename)
        elif trailer_new_file_path != trailer_old_file_path and await aiofiles.os.path.exists(trailer_new_file_path):
            await move_file_async(trailer_new_file_path, trailer_new_file_path_with_filename)
        else:
            trailer_exists = False

        if trailer_exists:
            Flags.file_done_dic[json_data["number"]].update({"local_trailer": trailer_new_file_path_with_filename})
            # 删除旧、新文件夹，用不到了(分集使用local trailer复制即可)
            if await aiofiles.os.path.exists(trailer_old_folder_path):
                shutil.rmtree(trailer_old_folder_path, ignore_errors=True)
            if trailer_new_folder_path != trailer_old_folder_path and await aiofiles.os.path.exists(
                trailer_new_folder_path
            ):
                shutil.rmtree(trailer_new_folder_path, ignore_errors=True)
            # 删除带文件名旧文件，用不到了
            if (
                trailer_old_file_path_with_filename != trailer_new_file_path_with_filename
                and await aiofiles.os.path.exists(trailer_old_file_path_with_filename)
            ):
                await delete_file_async(trailer_old_file_path_with_filename)
        else:
            local_trailer = Flags.file_done_dic.get(json_data["number"], {}).get("local_trailer")
            if local_trailer and await aiofiles.os.path.exists(local_trailer):
                await copy_file_async(local_trailer, trailer_new_file_path_with_filename)

    # 处理 extrafanart、extrafanart副本、主题视频、附加视频
    if single_folder_catched:
        # 处理 extrafanart
        try:
            if await aiofiles.os.path.exists(extrafanart_new_path):
                if extrafanart_old_path.lower() != extrafanart_new_path.lower() and await aiofiles.os.path.exists(
                    extrafanart_old_path
                ):
                    shutil.rmtree(extrafanart_old_path, ignore_errors=True)
            elif await aiofiles.os.path.exists(extrafanart_old_path):
                await move_file_async(extrafanart_old_path, extrafanart_new_path)
        except Exception:
            signal.show_log_text(traceback.format_exc())

        # extrafanart副本
        try:
            if await aiofiles.os.path.exists(extrafanart_copy_new_path):
                if (
                    extrafanart_copy_old_path.lower() != extrafanart_copy_new_path.lower()
                    and await aiofiles.os.path.exists(extrafanart_copy_old_path)
                ):
                    shutil.rmtree(extrafanart_copy_old_path, ignore_errors=True)
            elif await aiofiles.os.path.exists(extrafanart_copy_old_path):
                await move_file_async(extrafanart_copy_old_path, extrafanart_copy_new_path)
        except Exception:
            signal.show_log_text(traceback.format_exc())

        # 主题视频
        if await aiofiles.os.path.exists(theme_videos_new_path):
            if theme_videos_old_path.lower() != theme_videos_new_path.lower() and await aiofiles.os.path.exists(
                theme_videos_old_path
            ):
                shutil.rmtree(theme_videos_old_path, ignore_errors=True)
        elif await aiofiles.os.path.exists(theme_videos_old_path):
            await move_file_async(theme_videos_old_path, theme_videos_new_path)

        # 附加视频
        if await aiofiles.os.path.exists(extrafanart_extra_new_path):
            if (
                extrafanart_extra_old_path.lower() != extrafanart_extra_new_path.lower()
                and await aiofiles.os.path.exists(extrafanart_extra_old_path)
            ):
                shutil.rmtree(extrafanart_extra_old_path, ignore_errors=True)
        elif await aiofiles.os.path.exists(extrafanart_extra_old_path):
            await move_file_async(extrafanart_extra_old_path, extrafanart_extra_new_path)

    return pic_final_catched, single_folder_catched
