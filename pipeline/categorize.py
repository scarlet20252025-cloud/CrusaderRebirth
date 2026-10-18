#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
按功能把解密后的数值表归类到 data/ 子目录。

用法:
    python categorize.py <输入目录> <输出目录>

输出目录结构:
    <输出>/character/  combat/  equipment/  hero/  item/  shop/
    <输出>/pvp/        stage/   event/      housing/     story/  text/
"""

import os
import shutil
import sys

CATEGORIES = {
    "character": [
        "character_stat", "character_visual", "characterclass", "character_parts",
        "character_profile", "character_addstatmax", "character_epiclevelstat",
        "npccharacter", "portraitdata", "fame",
    ],
    "combat": [
        "battlesettings", "battlestatistics", "addstate", "skill", "spskill",
        "projectile", "pattern", "visualeffect", "bosspassive", "worldrules",
        "addstatitem", "boostmode_info", "regen_time",
    ],
    "equipment": [
        "weapon", "weapon_convert_cost", "weapon_convert_exclusive_option",
        "weapon_convert_list", "weapon_dismantle_props", "weapon_gradeup_cost",
        "weapon_sell_cost", "accessory_earring", "accessory_enhance",
        "accessory_necklace", "accessory_option", "accessory_set",
        "accessory_settings", "ring", "ring_sell_cost", "ringoption",
        "ringoptionhelp", "add_weapon_socket_info", "add_weapon_socket_material",
        "inheritbook", "resetinherit",
    ],
    "hero": [
        "champion", "champion_domain", "champion_domainmaxlevelreward",
        "champion_link_level_stat_unlock", "champion_skill", "champion_slot",
        "champion_supply", "champion_unlock", "hero_bookroom_main",
        "hero_bookroom_sub", "hero_bookunlock", "hero_easteregg",
        "hero_sell_cost", "hero_trainingpoint", "hero_upgrade_cost",
        "herolevelupcost", "heropass_eventdialogue", "heropass_eventmission",
        "heropass_settings", "level_props", "user_level_reward",
        "contents_unlock", "dummy",
    ],
    "item": [
        "item", "material", "bread", "buffitem", "mix", "oven", "boxgacha",
        "boxgachalist", "bundlebox", "randombox", "choice_gacha", "gacha",
        "pointdrop", "dummybackground", "autolocklist",
    ],
    "shop": [
        "gypsi", "house_shop", "orchard_shop", "content_event_shop",
        "content_event_shopinfo", "luckyshopevent_prize",
        "luckyshopevent_product", "timepackage", "vip", "inapp_profile",
        "inventory", "inventory_discount_info", "resourcediscountrate",
        "dataswap", "auctioncomment", "auctioneventsetting",
    ],
    "pvp": [
        "arenainfo", "arena_settings", "arena_week_reward", "pvp_itemlist",
        "pvp_roundreward", "pvp_weekreward", "greedwar_public_option",
        "greedwaraddreward", "greedwarbasicreward", "greedwarhelpinfo",
        "totalwarstage", "wargameaddreward", "wargamehelpinfo", "wargametileinfo",
    ],
    "stage": [
        "stage", "stage_dungeon", "stage_episode", "stage_kurenai",
        "stage_restriction", "stage_reward", "stage_soul", "stage_theme",
        "chapter", "chapter_binder_challenge", "chapter_binder_episode",
        "quest_goal", "rankquest", "storyquest", "periodquest",
        "last_quest_detail", "last_quest_group", "last_quest_tab",
        "questrankinfo", "pathselection", "episodereward", "repeat_raid_reward",
    ],
    "event": [
        "contentseventquest", "chocolaeventbread", "chocolaeventbreaddialogue",
        "chocolaeventbreaddialoguegroup", "chocolaeventbreadimage",
        "chocolaeventbreadingredient", "chocolaeventpointrules",
        "chocolaeventsalesreward", "chocolaeventstarreward",
        "roguelikeeventachievement", "roguelikeeventbuff",
        "roguelikeeventcharacter", "roguelikeeventcharacterlevel",
        "roguelikeeventstageinfo", "roguelikeeventstagestat",
        "roguelikeeventwave", "story_event_contents", "story_event_reward",
        "rhythm_event_contents", "rhythm_event_hitlevel",
        "rhythm_event_interaction", "rhythm_event_music",
        "rhythm_event_reward", "westeventclearreward", "daily_hottime_reward",
        "retentionreward", "reward_event_info", "bingo_cell_reward",
        "bingo_complete_reward", "bingopass_settings",
    ],
    "housing": [
        "house_ani_set", "house_item", "orchard", "orchardcondition",
        "orchardconditiongroup", "orchardfruit", "orchardreward", "orchardshop",
        "fishery", "fish", "fishinggear", "fishinglevel", "fishingsetting",
        "carvestone", "carvestone_option", "carvestone_set",
    ],
    "story": [
        "dialogue", "dialogue_event", "dialogues_category", "dialoguetalkjson1",
        "dialoguetalkjson2", "dialoguetalkjson3", "talk_dialogue_group",
        "cutscene", "cutscene_bgm", "cutscene_viewer_main",
        "cutscene_viewer_season", "cutscene_viewer_sub",
        "cutscene_viewer_subcontents", "cutscene_weaponoff_cha",
        "endingcredit", "oztalkchatinfo", "oztalkdatemain", "oztalkdialogue",
        "oztalkfamiliarity", "oztalkmain", "oztalkprofile", "oztalkselect",
        "sister", "sisterevent", "usermessage", "terms", "help",
        "tip_chaptergroup", "tip_img", "tip_text", "chatsticker",
        "illustcollection", "illustcollectionunlock", "library",
        "libraryrecord", "sound", "costume", "fameportraitborder",
        "famemonument", "friendshipreward", "cqsimyilist",
        "maze_exploration_reward", "pass_goal_reward",
        "screen_pattern_helper", "screen_pattern_setting", "versions",
    ],
    "text": [],   # get_text* 前缀自动归入
}

# 反查表
LOOKUP = {}
for cat, names in CATEGORIES.items():
    for n in names:
        LOOKUP[n] = cat


def category_of(stem: str) -> str:
    """根据文件名主干返回分类。"""
    if stem.startswith("get_text"):
        return "text"
    key = stem[4:] if stem.startswith("get_") else stem
    return LOOKUP.get(key, "_misc")


def main():
    if len(sys.argv) < 3:
        sys.exit("用法: python categorize.py <输入目录> <输出目录>")

    src, dst = sys.argv[1], sys.argv[2]

    moved = 0
    misc = []

    for fn in sorted(os.listdir(src)):
        if not fn.endswith(".json"):
            continue
        stem = fn[:-5]
        cat = category_of(stem)
        if cat == "_misc":
            misc.append(stem)
        out_dir = os.path.join(dst, cat)
        os.makedirs(out_dir, exist_ok=True)
        shutil.copy2(os.path.join(src, fn), os.path.join(out_dir, fn))
        moved += 1

    print("已归类 %d 个文件" % moved)
    if misc:
        print("未归类 (%d): %s" % (len(misc), ", ".join(misc)))

    print("\n分类统计:")
    for cat in sorted(os.listdir(dst)):
        p = os.path.join(dst, cat)
        if not os.path.isdir(p):
            continue
        files = [f for f in os.listdir(p) if f.endswith(".json")]
        size = sum(os.path.getsize(os.path.join(p, f)) for f in files)
        print("  %-12s %3d files  %7.2f MB" % (cat, len(files), size / 1024 / 1024))


if __name__ == "__main__":
    main()
