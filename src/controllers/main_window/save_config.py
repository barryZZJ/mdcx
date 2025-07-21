import os
import platform
import re
import traceback
from typing import TYPE_CHECKING, cast

from PyQt5.QtCore import Qt

from models.base.utils import convert_path
from models.config.manager import config, manager
from models.core.flags import Flags
from models.core.utils import get_movie_path_setting
from models.core.web import check_proxyChange
from models.signals import signal
from models.tools.actress_db import ActressDB

from .bind_utils import get_checkbox, get_checkboxes, get_radio_buttons

if TYPE_CHECKING:
    from views.MDCx import Ui_MDCx


def save_config(self):
    """
    从 UI 获取配置并保存到 config 对象中, 并更新配置文件
    """
    self.Ui = cast("Ui_MDCx", self.Ui)
    # region media & escape
    config.media_path = self.Ui.lineEdit_movie_path.text()  # 待刮削目录
    config.softlink_path = self.Ui.lineEdit_movie_softlink_path.text()  # 软链接目录目录
    config.success_output_folder = self.Ui.lineEdit_success.text()  # 成功输出目录
    config.failed_output_folder = self.Ui.lineEdit_fail.text()  # 失败输出目录
    config.extrafanart_folder = self.Ui.lineEdit_extrafanart_dir.text().strip()  # 剧照目录
    config.media_type = self.Ui.lineEdit_movie_type.text().lower()  # 视频格式
    config.sub_type = self.Ui.lineEdit_sub_type.text()  # 字幕格式
    config.folders = self.Ui.lineEdit_escape_dir.text()  # 排除文件夹
    config.string = self.Ui.lineEdit_escape_string.text()  # 过滤字符
    config.scrape_softlink_path = get_checkbox(self.Ui.checkBox_scrape_softlink_path)

    try:  # 过滤小文件大小
        config.file_size = float(self.Ui.lineEdit_escape_size.text())
    except Exception:
        config.file_size = 0.0
    config.no_escape = get_checkboxes(
        (self.Ui.checkBox_no_escape_file, "no_skip_small_file"),
        (self.Ui.checkBox_no_escape_dir, "folder"),
        (self.Ui.checkBox_skip_success_file, "skip_success_file"),
        (self.Ui.checkBox_skip_success_file_except, "scrape_success_file"),
        (self.Ui.checkBox_record_success_file, "record_success_file"),
        (self.Ui.checkBox_check_symlink, "check_symlink"),
        (self.Ui.checkBox_check_symlink_definition, "symlink_definition"),
    )
    # endregion

    # region clean
    config.clean_ext = self.Ui.lineEdit_clean_file_ext.text().strip(" |｜")  # 清理扩展名
    config.clean_name = self.Ui.lineEdit_clean_file_name.text().strip(" |｜")  # 清理文件名
    config.clean_contains = self.Ui.lineEdit_clean_file_contains.text().strip(" |｜")  # 清理文件名包含
    try:
        config.clean_size = float(self.Ui.lineEdit_clean_file_size.text().strip(" |｜"))  # 清理文件大小小于等于
    except Exception:
        config.clean_size = 0.0
    config.clean_ignore_ext = self.Ui.lineEdit_clean_excluded_file_ext.text().strip(" |｜")  # 不清理扩展名
    config.clean_ignore_contains = self.Ui.lineEdit_clean_excluded_file_contains.text().strip(
        " |｜"
    )  # 不清理文件名包含
    config.clean_enable = get_checkboxes(
        (self.Ui.checkBox_clean_file_ext, "clean_ext"),
        (self.Ui.checkBox_clean_file_name, "clean_name"),
        (self.Ui.checkBox_clean_file_contains, "clean_contains"),
        (self.Ui.checkBox_clean_file_size, "clean_size"),
        (self.Ui.checkBox_clean_excluded_file_ext, "clean_ignore_ext"),
        (self.Ui.checkBox_clean_excluded_file_contains, "clean_ignore_contains"),
        (self.Ui.checkBox_i_understand_clean, "i_know"),
        (self.Ui.checkBox_i_agree_clean, "i_agree"),
        (self.Ui.checkBox_auto_clean, "auto_clean"),
    )
    # endregion

    # region website
    config.website_single = self.Ui.comboBox_website_all.currentText()  # 指定单个网站
    config.website_youma = self.Ui.lineEdit_website_youma.text()  # 有码番号刮削网站
    config.website_wuma = self.Ui.lineEdit_website_wuma.text()  # 无码番号刮削网站
    config.website_suren = self.Ui.lineEdit_website_suren.text()  # 素人番号刮削网站
    config.website_fc2 = self.Ui.lineEdit_website_fc2.text()  # FC2番号刮削网站
    config.website_oumei = self.Ui.lineEdit_website_oumei.text()  # 欧美番号刮削网站
    config.website_guochan = self.Ui.lineEdit_website_guochan.text()  # 国产番号刮削网站

    config.scrape_like = get_radio_buttons(
        (self.Ui.radioButton_scrape_speed, "speed"), (self.Ui.radioButton_scrape_info, "info"), default="single"
    )

    config.website_set = get_checkboxes(
        (self.Ui.checkBox_use_official_data, "official"),
    )
    config.title_website = self.Ui.lineEdit_title_website.text()  # 标题字段网站优先级
    config.title_zh_website = self.Ui.lineEdit_title_zh_website.text()  # 中文标题字段网站优先级
    config.title_website_exclude = self.Ui.lineEdit_title_website_exclude.text()  # 标题字段排除网站
    config.title_language = get_radio_buttons(
        (self.Ui.radioButton_title_zh_cn, "zh_cn"), (self.Ui.radioButton_title_zh_tw, "zh_tw"), default="jp"
    )
    config.title_sehua = get_checkbox(self.Ui.checkBox_title_sehua)
    config.title_yesjav = get_checkbox(self.Ui.checkBox_title_yesjav)
    config.title_translate = get_checkbox(self.Ui.checkBox_title_translate)
    config.title_sehua_zh = get_checkbox(self.Ui.checkBox_title_sehua_2)

    config.outline_website = self.Ui.lineEdit_outline_website.text()  # 简介字段网站优先级
    config.outline_zh_website = self.Ui.lineEdit_outline_zh_website.text()  # 中文简介字段网站优先级
    config.outline_website_exclude = self.Ui.lineEdit_outline_website_exclude.text()  # 简介字段排除网站
    config.outline_language = get_radio_buttons(
        (self.Ui.radioButton_outline_zh_cn, "zh_cn"), (self.Ui.radioButton_outline_zh_tw, "zh_tw"), default="jp"
    )
    config.outline_translate = get_checkbox(self.Ui.checkBox_outline_translate)
    config.outline_show = get_checkboxes(
        (self.Ui.checkBox_show_translate_from, "show_from"),
        (self.Ui.radioButton_trans_show_zh_jp, "show_zh_jp"),
        (self.Ui.radioButton_trans_show_jp_zh, "show_jp_zh"),
    )

    config.actor_website = self.Ui.lineEdit_actor_website.text()  # 演员字段网站优先级
    config.actor_website_exclude = self.Ui.lineEdit_actor_website_exclude.text()  # 演员字段排除网站
    config.actor_language = get_radio_buttons(
        (self.Ui.radioButton_actor_zh_cn, "zh_cn"), (self.Ui.radioButton_actor_zh_tw, "zh_tw"), default="jp"
    )
    config.actor_realname = get_checkbox(self.Ui.checkBox_actor_realname)
    config.actor_translate = get_checkbox(self.Ui.checkBox_actor_translate)

    config.tag_website = self.Ui.lineEdit_tag_website.text()  # 标签字段网站优先级
    config.tag_website_exclude = self.Ui.lineEdit_tag_website_exclude.text()  # 标签字段排除网站
    config.tag_language = get_radio_buttons(
        (self.Ui.radioButton_tag_zh_cn, "zh_cn"), (self.Ui.radioButton_tag_zh_tw, "zh_tw"), default="jp"
    )
    config.tag_translate = get_checkbox(self.Ui.checkBox_tag_translate)

    config.tag_include = get_checkboxes(
        (self.Ui.checkBox_tag_actor, "actor"),
        (self.Ui.checkBox_tag_letters, "letters"),
        (self.Ui.checkBox_tag_series, "series"),
        (self.Ui.checkBox_tag_studio, "studio"),
        (self.Ui.checkBox_tag_publisher, "publisher"),
        (self.Ui.checkBox_tag_cnword, "cnword"),
        (self.Ui.checkBox_tag_mosaic, "mosaic"),
        (self.Ui.checkBox_tag_definition, "definition"),
    )

    config.series_website = self.Ui.lineEdit_series_website.text()  # 系列字段网站优先级
    config.series_website_exclude = self.Ui.lineEdit_series_website_exclude.text()  # 系列字段排除网站
    config.series_language = get_radio_buttons(
        (self.Ui.radioButton_series_zh_cn, "zh_cn"),
        (self.Ui.radioButton_series_zh_tw, "zh_tw"),
        default="jp",
    )
    config.series_translate = get_checkbox(self.Ui.checkBox_series_translate)

    config.studio_website = self.Ui.lineEdit_studio_website.text()  # 片商字段网站优先级
    config.studio_website_exclude = self.Ui.lineEdit_studio_website_exclude.text()  # 片商字段排除网站
    config.studio_language = get_radio_buttons(
        (self.Ui.radioButton_studio_zh_cn, "zh_cn"),
        (self.Ui.radioButton_studio_zh_tw, "zh_tw"),
        default="jp",
    )
    config.studio_translate = get_checkbox(self.Ui.checkBox_studio_translate)

    config.publisher_website = self.Ui.lineEdit_publisher_website.text()  # 发行字段网站优先级
    config.publisher_website_exclude = self.Ui.lineEdit_publisher_website_exclude.text()  # 发行字段排除网站
    config.publisher_language = get_radio_buttons(
        (self.Ui.radioButton_publisher_zh_cn, "zh_cn"),
        (self.Ui.radioButton_publisher_zh_tw, "zh_tw"),
        default="jp",
    )
    config.publisher_translate = get_checkbox(self.Ui.checkBox_publisher_translate)

    config.director_website = self.Ui.lineEdit_director_website.text()  # 导演字段网站优先级
    config.director_website_exclude = self.Ui.lineEdit_director_website_exclude.text()  # 导演字段排除网站
    config.director_language = get_radio_buttons(
        (self.Ui.radioButton_director_zh_cn, "zh_cn"), (self.Ui.radioButton_director_zh_tw, "zh_tw"), default="jp"
    )
    config.director_translate = get_checkbox(self.Ui.checkBox_director_translate)

    config.poster_website = self.Ui.lineEdit_poster_website.text()  # 封面字段网站优先级
    config.poster_website_exclude = self.Ui.lineEdit_poster_website_exclude.text()  # 封面字段排除网站
    config.thumb_website = self.Ui.lineEdit_thumb_website.text()  # 背景字段网站优先级
    config.thumb_website_exclude = self.Ui.lineEdit_thumb_website_exclude.text()  # 背景字段排除网站
    config.extrafanart_website = self.Ui.lineEdit_extrafanart_website.text()  # 剧照字段网站优先级
    config.extrafanart_website_exclude = self.Ui.lineEdit_extrafanart_website_exclude.text()  # 剧照字段排除网站
    config.score_website = self.Ui.lineEdit_score_website.text()  # 评分字段网站优先级
    config.score_website_exclude = self.Ui.lineEdit_score_website_exclude.text()  # 评分字段排除网站
    config.release_website = self.Ui.lineEdit_release_website.text()  # 发行日期字段网站优先级
    config.release_website_exclude = self.Ui.lineEdit_release_website_exclude.text()  # 发行日期字段排除网站
    config.runtime_website = self.Ui.lineEdit_runtime_website.text()  # 时长字段网站优先级
    config.runtime_website_exclude = self.Ui.lineEdit_runtime_website_exclude.text()  # 时长字段排除网站
    config.trailer_website = self.Ui.lineEdit_trailer_website.text()  # 预告片字段网站优先级
    config.trailer_website_exclude = self.Ui.lineEdit_trailer_website_exclude.text()  # 预告片字段排除网站
    config.wanted_website = self.Ui.lineEdit_wanted_website.text()  # 想看人数网站
    config.nfo_tagline = self.Ui.lineEdit_nfo_tagline.text()  # tagline格式
    config.nfo_tag_series = self.Ui.lineEdit_nfo_tag_series.text()  # nfo_tag_series 格式
    config.nfo_tag_studio = self.Ui.lineEdit_nfo_tag_studio.text()  # nfo_tag_studio 格式
    config.nfo_tag_publisher = self.Ui.lineEdit_nfo_tag_publisher.text()  # nfo_tag_publisher 格式
    config.nfo_tag_actor = self.Ui.lineEdit_nfo_tag_actor.text()  # nfo_tag_actor 格式
    config.nfo_tag_actor_contains = self.Ui.lineEdit_nfo_tag_actor_contains.text().strip(
        " |｜"
    )  # nfo_tag_actor_contains 格式

    config.whole_fields = get_checkboxes(
        (self.Ui.radioButton_outline_more, "outline"),
        (self.Ui.radioButton_actor_more, "actor"),
        (self.Ui.radioButton_thumb_more, "thumb"),
        (self.Ui.radioButton_poster_more, "poster"),
        (self.Ui.radioButton_extrafanart_more, "extrafanart"),
        (self.Ui.radioButton_trailer_more, "trailer"),
        (self.Ui.radioButton_release_more, "release"),
        (self.Ui.radioButton_runtime_more, "runtime"),
        (self.Ui.radioButton_score_more, "score"),
        (self.Ui.radioButton_tag_more, "tag"),
        (self.Ui.radioButton_director_more, "director"),
        (self.Ui.radioButton_series_more, "series"),
        (self.Ui.radioButton_studio_more, "studio"),
        (self.Ui.radioButton_publisher_more, "publisher"),
    )

    config.none_fields = get_checkboxes(
        (self.Ui.radioButton_outline_none, "outline"),
        (self.Ui.radioButton_actor_none, "actor"),
        (self.Ui.radioButton_thumb_none, "thumb"),
        (self.Ui.radioButton_poster_none, "poster"),
        (self.Ui.radioButton_extrafanart_none, "extrafanart"),
        (self.Ui.radioButton_trailer_none, "trailer"),
        (self.Ui.radioButton_release_none, "release"),
        (self.Ui.radioButton_runtime_none, "runtime"),
        (self.Ui.radioButton_score_none, "score"),
        (self.Ui.radioButton_tag_none, "tag"),
        (self.Ui.radioButton_director_none, "director"),
        (self.Ui.radioButton_series_none, "series"),
        (self.Ui.radioButton_studio_none, "studio"),
        (self.Ui.radioButton_publisher_none, "publisher"),
        (self.Ui.radioButton_wanted_none, "wanted"),
    )

    # region nfo
    config.nfo_include_new = get_checkboxes(
        (self.Ui.checkBox_nfo_sorttitle, "sorttitle"),
        (self.Ui.checkBox_nfo_originaltitle, "originaltitle"),
        (self.Ui.checkBox_nfo_title_cd, "title_cd"),
        (self.Ui.checkBox_nfo_outline, "outline"),
        (self.Ui.checkBox_nfo_plot, "plot_"),
        (self.Ui.checkBox_nfo_originalplot, "originalplot"),
        (self.Ui.checkBox_outline_cdata, "outline_no_cdata"),
        (self.Ui.checkBox_nfo_release, "release_"),
        (self.Ui.checkBox_nfo_relasedate, "releasedate"),
        (self.Ui.checkBox_nfo_premiered, "premiered"),
        (self.Ui.checkBox_nfo_country, "country"),
        (self.Ui.checkBox_nfo_mpaa, "mpaa"),
        (self.Ui.checkBox_nfo_customrating, "customrating"),
        (self.Ui.checkBox_nfo_year, "year"),
        (self.Ui.checkBox_nfo_runtime, "runtime"),
        (self.Ui.checkBox_nfo_wanted, "wanted"),
        (self.Ui.checkBox_nfo_score, "score"),
        (self.Ui.checkBox_nfo_criticrating, "criticrating"),
        (self.Ui.checkBox_nfo_actor, "actor"),
        (self.Ui.checkBox_nfo_all_actor, "actor_all"),
        (self.Ui.checkBox_nfo_director, "director"),
        (self.Ui.checkBox_nfo_series, "series"),
        (self.Ui.checkBox_nfo_tag, "tag"),
        (self.Ui.checkBox_nfo_genre, "genre"),
        (self.Ui.checkBox_nfo_actor_set, "actor_set"),
        (self.Ui.checkBox_nfo_set, "series_set"),
        (self.Ui.checkBox_nfo_studio, "studio"),
        (self.Ui.checkBox_nfo_maker, "maker"),
        (self.Ui.checkBox_nfo_publisher, "publisher"),
        (self.Ui.checkBox_nfo_label, "label"),
        (self.Ui.checkBox_nfo_poster, "poster"),
        (self.Ui.checkBox_nfo_cover, "cover"),
        (self.Ui.checkBox_nfo_trailer, "trailer"),
        (self.Ui.checkBox_nfo_website, "website"),
    )
    # endregion
    config.translate_by = get_checkboxes(
        (self.Ui.checkBox_youdao, "youdao"),
        (self.Ui.checkBox_google, "google"),
        (self.Ui.checkBox_deepl, "deepl"),
        (self.Ui.checkBox_llm, "llm"),
    )
    config.deepl_key = self.Ui.lineEdit_deepl_key.text()  # deepl key

    config.llm_url = self.Ui.lineEdit_llm_url.text()
    config.llm_model = self.Ui.lineEdit_llm_model.text()
    config.llm_key = self.Ui.lineEdit_llm_key.text()
    config.llm_prompt = self.Ui.textEdit_llm_prompt.toPlainText()
    config.llm_max_req_sec = self.Ui.doubleSpinBox_llm_max_req_sec.value()
    config.llm_max_try = self.Ui.spinBox_llm_max_try.value()
    config.llm_temperature = self.Ui.doubleSpinBox_llm_temperature.value()
    # endregion

    # region common
    config.thread_number = self.Ui.horizontalSlider_thread.value()  # 线程数量
    config.thread_time = self.Ui.horizontalSlider_thread_time.value()  # 线程延时
    config.javdb_time = self.Ui.horizontalSlider_javdb_time.value()  # javdb 延时
    # 主模式设置
    config.main_mode = get_radio_buttons(
        (self.Ui.radioButton_mode_common, 1),
        (self.Ui.radioButton_mode_sort, 2),
        (self.Ui.radioButton_mode_update, 3),
        (self.Ui.radioButton_mode_read, 4),
        default=1,
    )

    config.read_mode = get_checkboxes(
        (self.Ui.checkBox_read_has_nfo_update, "has_nfo_update"),
        (self.Ui.checkBox_read_no_nfo_scrape, "no_nfo_scrape"),
        (self.Ui.checkBox_read_download_file_again, "read_download_again"),
        (self.Ui.checkBox_read_update_nfo, "read_update_nfo"),
    )
    # update 模式设置
    if self.Ui.radioButton_update_c.isChecked():
        config.update_mode = "c"
    elif self.Ui.radioButton_update_b_c.isChecked():
        config.update_mode = "abc" if self.Ui.checkBox_update_a.isChecked() else "bc"
    elif self.Ui.radioButton_update_d_c.isChecked():
        config.update_mode = "d"
    else:
        config.update_mode = "c"
    config.update_a_folder = self.Ui.lineEdit_update_a_folder.text()  # 更新模式 - a 目录
    config.update_b_folder = self.Ui.lineEdit_update_b_folder.text()  # 更新模式 - b 目录
    config.update_c_filetemplate = self.Ui.lineEdit_update_c_filetemplate.text()  # 更新模式 - c 文件命名规则
    config.update_d_folder = self.Ui.lineEdit_update_d_folder.text()  # 更新模式 - d 目录
    config.update_titletemplate = self.Ui.lineEdit_update_titletemplate.text()  # 更新模式 - emby视频标题
    # 链接模式设置
    if self.Ui.radioButton_soft_on.isChecked():  # 软链接开
        config.soft_link = 1
    elif self.Ui.radioButton_hard_on.isChecked():  # 硬链接开
        config.soft_link = 2
    else:  # 软链接关
        config.soft_link = 0

    # 文件操作设置
    config.success_file_move = self.Ui.radioButton_succ_move_on.isChecked()
    config.failed_file_move = self.Ui.radioButton_fail_move_on.isChecked()
    config.success_file_rename = self.Ui.radioButton_succ_rename_on.isChecked()
    config.del_empty_folder = self.Ui.radioButton_del_empty_folder_on.isChecked()
    config.show_poster = self.Ui.checkBox_cover.isChecked()
    # endregion

    # region download
    config.download_files = "," + get_checkboxes(
        (self.Ui.checkBox_download_poster, "poster"),
        (self.Ui.checkBox_download_thumb, "thumb"),
        (self.Ui.checkBox_download_fanart, "fanart"),
        (self.Ui.checkBox_download_extrafanart, "extrafanart"),
        (self.Ui.checkBox_download_trailer, "trailer"),
        (self.Ui.checkBox_download_nfo, "nfo"),
        (self.Ui.checkBox_extras, "extrafanart_extras"),
        (self.Ui.checkBox_download_extrafanart_copy, "extrafanart_copy"),
        (self.Ui.checkBox_theme_videos, "theme_videos"),
        (self.Ui.checkBox_ignore_pic_fail, "ignore_pic_fail"),
        (self.Ui.checkBox_ignore_youma, "ignore_youma"),
        (self.Ui.checkBox_ignore_wuma, "ignore_wuma"),
        (self.Ui.checkBox_ignore_fc2, "ignore_fc2"),
        (self.Ui.checkBox_ignore_guochan, "ignore_guochan"),
        (self.Ui.checkBox_ignore_size, "ignore_size"),
    )

    config.keep_files = "," + get_checkboxes(
        (self.Ui.checkBox_old_poster, "poster"),
        (self.Ui.checkBox_old_thumb, "thumb"),
        (self.Ui.checkBox_old_fanart, "fanart"),
        (self.Ui.checkBox_old_extrafanart, "extrafanart"),
        (self.Ui.checkBox_old_trailer, "trailer"),
        (self.Ui.checkBox_old_nfo, "nfo"),
        (self.Ui.checkBox_old_extrafanart_copy, "extrafanart_copy"),
        (self.Ui.checkBox_old_theme_videos, "theme_videos"),
    )

    config.download_hd_pics = get_checkboxes(
        (self.Ui.checkBox_hd_poster, "poster"),
        (self.Ui.checkBox_hd_thumb, "thumb"),
        (self.Ui.checkBox_amazon_big_pic, "amazon"),
        (self.Ui.checkBox_official_big_pic, "official"),
        (self.Ui.checkBox_google_big_pic, "google"),
        (self.Ui.radioButton_google_only, "goo_only"),
    )

    config.google_used = self.Ui.lineEdit_google_used.text()  # google 下载词
    config.google_exclude = self.Ui.lineEdit_google_exclude.text()  # google 过滤词
    # endregion

    # region name
    config.folder_name = self.Ui.lineEdit_dir_name.text()  # 视频文件夹命名
    config.naming_file = self.Ui.lineEdit_local_name.text()  # 视频文件名命名
    config.naming_media = self.Ui.lineEdit_media_name.text()  # nfo标题命名
    config.prevent_char = self.Ui.lineEdit_prevent_char.text()  # 防屏蔽字符

    config.fields_rule = get_checkboxes(
        (self.Ui.checkBox_title_del_actor, "del_actor"),
        (self.Ui.checkBox_actor_del_char, "del_char"),
        (self.Ui.checkBox_actor_fc2_seller, "fc2_seller"),
        (self.Ui.checkBox_number_del_num, "del_num"),
    )
    config.suffix_sort = self.Ui.lineEdit_suffix_sort.text()  # 后缀字段顺序
    config.actor_no_name = self.Ui.lineEdit_actor_no_name.text()  # 未知演员
    config.actor_name_more = self.Ui.lineEdit_actor_name_more.text()  # 等演员
    release_rule = self.Ui.lineEdit_release_rule.text()  # 发行日期
    config.release_rule = re.sub(r'[\\/:*?"<>|\r\n]+', "-", release_rule).strip()

    config.folder_name_max = int(self.Ui.lineEdit_folder_name_max.text())  # 长度命名规则-目录
    config.file_name_max = int(self.Ui.lineEdit_file_name_max.text())  # 长度命名规则-文件名
    config.actor_name_max = int(self.Ui.lineEdit_actor_name_max.text())  # 长度命名规则-演员数量

    config.umr_style = self.Ui.lineEdit_umr_style.text()  # 无码破解版本命名
    config.leak_style = self.Ui.lineEdit_leak_style.text()  # 无码流出版本命名
    config.wuma_style = self.Ui.lineEdit_wuma_style.text()  # 无码版本命名
    config.youma_style = self.Ui.lineEdit_youma_style.text()  # 有码版本命名
    config.show_moword = get_checkboxes(
        (self.Ui.checkBox_foldername_mosaic, "folder"),
        (self.Ui.checkBox_filename_mosaic, "file"),
    )
    config.show_4k = get_checkboxes(
        (self.Ui.checkBox_foldername_4k, "folder"),
        (self.Ui.checkBox_filename_4k, "file"),
    )

    # 分集命名规则
    config.cd_name = get_radio_buttons(
        (self.Ui.radioButton_cd_part_lower, 0),
        (self.Ui.radioButton_cd_part_upper, 1),
        default=2,
    )

    config.cd_char = get_checkboxes(
        (self.Ui.checkBox_cd_part_a, "letter"),
        (self.Ui.checkBox_cd_part_c, "endc"),
        (self.Ui.checkBox_cd_part_01, "digital"),
        (self.Ui.checkBox_cd_part_1_xxx, "middle_number"),
        (self.Ui.checkBox_cd_part_underline, "underline"),
        (self.Ui.checkBox_cd_part_space, "space"),
        (self.Ui.checkBox_cd_part_point, "point"),
    )

    # 图片和预告片命名规则
    config.pic_simple_name = not self.Ui.radioButton_pic_with_filename.isChecked()
    config.trailer_simple_name = not self.Ui.radioButton_trailer_with_filename.isChecked()
    config.hd_name = "height" if self.Ui.radioButton_definition_height.isChecked() else "hd"

    # 分辨率获取方式
    config.hd_get = get_radio_buttons(
        (self.Ui.radioButton_videosize_video, "video"),
        (self.Ui.radioButton_videosize_path, "path"),
        default="none",
    )
    # endregion

    # region subtitle
    config.cnword_char = self.Ui.lineEdit_cnword_char.text()  # 中文字幕判断字符
    config.cnword_style = self.Ui.lineEdit_cnword_style.text()  # 中文字幕字符样式
    config.folder_cnword = get_checkbox(self.Ui.checkBox_foldername)
    config.file_cnword = get_checkbox(self.Ui.checkBox_filename)
    config.subtitle_folder = self.Ui.lineEdit_sub_folder.text()  # 字幕文件目录
    config.subtitle_add = get_checkbox(self.Ui.radioButton_add_sub_on)
    config.subtitle_add_chs = get_checkbox(self.Ui.checkBox_sub_add_chs)
    config.subtitle_add_rescrape = get_checkbox(self.Ui.checkBox_sub_rescrape)
    # endregion

    # region emby
    config.server_type = "emby" if self.Ui.radioButton_server_emby.isChecked() else "jellyfin"
    config.emby_url = self.Ui.lineEdit_emby_url.text()  # emby地址
    config.emby_url = config.emby_url.replace("：", ":").strip("/ ")
    if config.emby_url and "://" not in config.emby_url:
        config.emby_url = "http://" + config.emby_url
    config.api_key = self.Ui.lineEdit_api_key.text()  # emby密钥
    config.user_id = self.Ui.lineEdit_user_id.text()  # emby用户ID
    config.actor_photo_folder = self.Ui.lineEdit_actor_photo_folder.text()  # 头像图片目录
    config.gfriends_github = self.Ui.lineEdit_net_actor_photo.text().strip(" /")  # gfriends github 项目地址
    config.info_database_path = self.Ui.lineEdit_actor_db_path.text()  # 信息数据库
    if not config.gfriends_github:
        config.gfriends_github = "https://github.com/gfriends/gfriends"
    elif "://" not in config.gfriends_github:
        config.gfriends_github = "https://" + config.gfriends_github
    config.use_database = 1 if self.Ui.checkBox_actor_db.isChecked() else 0
    if config.use_database:
        ActressDB.init_db()

    # 构建 emby_on 配置字符串
    actor_info_lang = get_radio_buttons(
        (self.Ui.radioButton_actor_info_zh_cn, "actor_info_zh_cn"),
        (self.Ui.radioButton_actor_info_zh_tw, "actor_info_zh_tw"),
        default="actor_info_ja",
    )
    actor_info_mode = get_radio_buttons(
        (self.Ui.radioButton_actor_info_all, "actor_info_all"), default="actor_info_miss"
    )
    actor_photo_source = get_radio_buttons(
        (self.Ui.radioButton_actor_photo_net, "actor_photo_net"), default="actor_photo_local"
    )
    actor_photo_mode = get_radio_buttons(
        (self.Ui.radioButton_actor_photo_all, "actor_photo_all"), default="actor_photo_miss"
    )

    config.emby_on = get_checkboxes(
        (True, actor_info_lang),
        (True, actor_info_mode),
        (True, actor_photo_source),
        (True, actor_photo_mode),
        (self.Ui.checkBox_actor_info_translate, "actor_info_translate"),
        (self.Ui.checkBox_actor_info_photo, "actor_info_photo"),
        (self.Ui.checkBox_actor_photo_ne_backdrop, "graphis_backdrop"),
        (self.Ui.checkBox_actor_photo_ne_face, "graphis_face"),
        (self.Ui.checkBox_actor_photo_ne_new, "graphis_new"),
        (self.Ui.checkBox_actor_photo_auto, "actor_photo_auto"),
        (self.Ui.checkBox_actor_pic_replace, "actor_replace"),
    )

    config.actor_photo_kodi_auto = get_checkbox(self.Ui.checkBox_actor_photo_kodi)
    # endregion

    # region mark
    config.poster_mark = 1 if self.Ui.checkBox_poster_mark.isChecked() else 0
    config.thumb_mark = 1 if self.Ui.checkBox_thumb_mark.isChecked() else 0
    config.fanart_mark = 1 if self.Ui.checkBox_fanart_mark.isChecked() else 0
    config.mark_size = self.Ui.horizontalSlider_mark_size.value()  # 水印大小

    config.mark_type = get_checkboxes(
        (self.Ui.checkBox_sub, "sub"),
        (self.Ui.checkBox_censored, "youma"),
        (self.Ui.checkBox_umr, "umr"),
        (self.Ui.checkBox_leak, "leak"),
        (self.Ui.checkBox_uncensored, "uncensored"),
        (self.Ui.checkBox_hd, "hd"),
    )

    # 水印位置设置
    config.mark_fixed = get_radio_buttons(
        (self.Ui.radioButton_not_fixed_position, "not_fixed"),
        (self.Ui.radioButton_fixed_corner, "corner"),
        default="fixed",
    )
    config.mark_pos = get_radio_buttons(
        (self.Ui.radioButton_top_left, "top_left"),
        (self.Ui.radioButton_top_right, "top_right"),
        (self.Ui.radioButton_bottom_left, "bottom_left"),
        (self.Ui.radioButton_bottom_right, "bottom_right"),
        default="top_left",
    )
    config.mark_pos_corner = get_radio_buttons(
        (self.Ui.radioButton_top_left_corner, "top_left"),
        (self.Ui.radioButton_top_right_corner, "top_right"),
        (self.Ui.radioButton_bottom_left_corner, "bottom_left"),
        (self.Ui.radioButton_bottom_right_corner, "bottom_right"),
        default="top_left",
    )
    config.mark_pos_hd = get_radio_buttons(
        (self.Ui.radioButton_top_left_hd, "top_left"),
        (self.Ui.radioButton_top_right_hd, "top_right"),
        (self.Ui.radioButton_bottom_left_hd, "bottom_left"),
        (self.Ui.radioButton_bottom_right_hd, "bottom_right"),
        default="top_left",
    )
    config.mark_pos_sub = get_radio_buttons(
        (self.Ui.radioButton_top_left_sub, "top_left"),
        (self.Ui.radioButton_top_right_sub, "top_right"),
        (self.Ui.radioButton_bottom_left_sub, "bottom_left"),
        (self.Ui.radioButton_bottom_right_sub, "bottom_right"),
        default="top_left",
    )
    config.mark_pos_mosaic = get_radio_buttons(
        (self.Ui.radioButton_top_left_mosaic, "top_left"),
        (self.Ui.radioButton_top_right_mosaic, "top_right"),
        (self.Ui.radioButton_bottom_left_mosaic, "bottom_left"),
        (self.Ui.radioButton_bottom_right_mosaic, "bottom_right"),
        default="top_left",
    )
    # endregion

    # region network
    config.type = get_radio_buttons(
        (self.Ui.radioButton_proxy_http, "http"),
        (self.Ui.radioButton_proxy_socks5, "socks5"),
        (self.Ui.radioButton_proxy_nouse, "no"),
        default="no",
    )
    proxy = self.Ui.lineEdit_proxy.text()  # 代理地址
    config.proxy = proxy.replace("https://", "").replace("http://", "")
    config.timeout = self.Ui.horizontalSlider_timeout.value()  # 超时时间
    config.retry = self.Ui.horizontalSlider_retry.value()  # 重试次数

    custom_website_name = self.Ui.comboBox_custom_website.currentText()
    custom_website_url = self.Ui.lineEdit_custom_website.text()
    if custom_website_url:
        custom_website_url = custom_website_url.strip("/ ")
        setattr(config, f"{custom_website_name}_website", custom_website_url)
    elif hasattr(config, f"{custom_website_name}_website"):
        delattr(config, f"{custom_website_name}_website")
    config.javdb = self.Ui.plainTextEdit_cookie_javdb.toPlainText()  # javdb cookie
    config.javbus = self.Ui.plainTextEdit_cookie_javbus.toPlainText()  # javbus cookie
    config.theporndb_api_token = self.Ui.lineEdit_api_token_theporndb.text()  # api token
    if config.javdb:
        config.javdb = config.javdb.replace("locale=en", "locale=zh")
    # endregion

    # region other
    config.rest_count = int(self.Ui.lineEdit_rest_count.text())  # 间歇刮削文件数量
    config.rest_time = self.Ui.lineEdit_rest_time.text()  # 间歇刮削休息时间
    config.timed_interval = self.Ui.lineEdit_timed_interval.text()  # 循环任务间隔时间

    # 开关汇总和其他设置
    show_logs_value = not self.Ui.textBrowser_log_main_2.isHidden()
    config.switch_on = get_checkboxes(
        (self.Ui.checkBox_auto_start, "auto_start"),
        (self.Ui.checkBox_auto_exit, "auto_exit"),
        (self.Ui.checkBox_rest_scrape, "rest_scrape"),
        (self.Ui.checkBox_timed_scrape, "timed_scrape"),
        (self.Ui.checkBox_remain_task, "remain_task"),
        (self.Ui.checkBox_show_dialog_exit, "show_dialog_exit"),
        (self.Ui.checkBox_show_dialog_stop_scrape, "show_dialog_stop_scrape"),
        (self.Ui.checkBox_sortmode_delpic, "sort_del"),
        (self.Ui.checkBox_net_ipv4_only, "ipv4_only"),
        (self.Ui.checkBox_dialog_qt, "qt_dialog"),
        (self.Ui.checkBox_theporndb_hash, "theporndb_no_hash"),
        (self.Ui.checkBox_hide_dock_icon, "hide_dock"),
        (self.Ui.checkBox_highdpi_passthrough, "passthrough"),
        (self.Ui.checkBox_hide_menu_icon, "hide_menu"),
        (self.Ui.checkBox_dark_mode, "dark_mode"),
        (self.Ui.checkBox_copy_netdisk_nfo, "copy_netdisk_nfo"),
    )

    # 手动添加 show_logs 设置
    if show_logs_value:
        config.switch_on += "show_logs,"

    # 添加隐藏设置
    hide_setting = get_radio_buttons(
        (self.Ui.radioButton_hide_close, "hide_close"),
        (self.Ui.radioButton_hide_mini, "hide_mini"),
        default="hide_none",
    )
    config.switch_on += f"{hide_setting},"

    # 日志设置
    config.show_web_log = get_checkbox(self.Ui.checkBox_show_web_log)
    config.show_from_log = get_checkbox(self.Ui.checkBox_show_from_log)
    config.show_data_log = get_checkbox(self.Ui.checkBox_show_data_log)
    config.save_log = get_radio_buttons(
        (self.Ui.radioButton_log_on, True),
        (self.Ui.radioButton_log_off, False),
        default=True,
    )
    config.update_check = get_radio_buttons(
        (self.Ui.radioButton_update_on, True),
        (self.Ui.radioButton_update_off, False),
        default=True,
    )
    config.local_library = self.Ui.lineEdit_local_library_path.text()  # 本地资源库
    config.actors_name = self.Ui.lineEdit_actors_name.text().replace("\n", "")  # 演员名
    config.netdisk_path = self.Ui.lineEdit_netdisk_path.text()  # 网盘路径
    config.localdisk_path = self.Ui.lineEdit_localdisk_path.text()  # 本地磁盘路径
    config.window_title = "hide" if self.Ui.checkBox_hide_window_title.isChecked() else "show"
    # endregion

    config.auto_link = get_checkbox(self.Ui.checkBox_create_link)  # 刮削中自动创建软链接

    config_folder: str = self.Ui.lineEdit_config_folder.text()  # 配置文件目录
    if not os.path.exists(config_folder):
        config_folder = manager.data_folder
    manager.path = convert_path(os.path.join(config_folder, manager.file))
    config.version = self.localversion
    manager.save_config()
    config.init()

    # 刮削偏好
    scrape_like = config.scrape_like
    if "speed" in scrape_like:
        Flags.scrape_like_text = "速度优先"
    elif "single" in scrape_like:
        Flags.scrape_like_text = "指定网站"
    else:
        Flags.scrape_like_text = "字段优先"

    main_mode = int(config.main_mode)  # 刮削模式
    mode_mapping = {
        1: ("common", "正常模式"),
        2: ("sort", "整理模式"),
        3: ("update", "更新模式"),
        4: ("read", "读取模式"),
    }

    mode_key, mode_text = mode_mapping.get(main_mode, ("common", "正常模式"))
    Flags.main_mode_text = mode_text

    try:
        scrape_like_text = Flags.scrape_like_text
        if config.scrape_like == "single":
            scrape_like_text += f" · {config.website_single}"
        if config.soft_link == 1:
            scrape_like_text += " · 软连接开"
        elif config.soft_link == 2:
            scrape_like_text += " · 硬连接开"
        signal.show_log_text(
            f" 🛠 当前配置：{manager.path} 保存完成！\n "
            f"📂 程序目录：{manager.data_folder} \n "
            f"📂 刮削目录：{get_movie_path_setting()[0]} \n "
            f"💠 刮削模式：{Flags.main_mode_text} · {scrape_like_text} \n "
            f"🖥️ 系统信息：{platform.platform()} \n "
            f"🐰 软件版本：{self.localversion} \n"
        )
    except Exception:
        signal.show_traceback_log(traceback.format_exc())
    try:
        check_proxyChange()  # 更新代理信息
        self._windows_auto_adjust()  # 界面自动调整
    except Exception:
        signal.show_traceback_log(traceback.format_exc())
    self.setWindowState(self.windowState() & ~Qt.WindowMinimized | Qt.WindowActive)  # type: ignore
    self.activateWindow()
    try:
        if config.scrape_success_folder_and_skip_link:
            self.set_label_file_path.emit(f"🎈 当前刮削路径: \n {get_movie_path_setting()[1]}")
        else:
            self.set_label_file_path.emit(f"🎈 当前刮削路径: \n {get_movie_path_setting()[0]}")  # 主界面右上角显示提示信息
    except Exception:
        signal.show_traceback_log(traceback.format_exc())
