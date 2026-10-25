# SW-DLT script, check Github for documentation.
# Official release on GitHub, avoid unknown sources

import urllib.parse
import subprocess
import importlib
import datetime
import hashlib
import shutil
import base64
import json
import sys
import os

# Constants class
class Consts:
    CYELLOW, CGREEN, CBLUE, SBOLD, ENDL = "\033[93m", "\033[92m", "\033[94m", "\033[1m", "\033[0m"
    DERROR_EXC = '{"output_code":"exception","exc_trace":"vars.downloadError"}'
    WORKSPACE = os.path.join(os.environ["HOME"], "Documents", "SW-DLT")
    VENV_PYTHON = os.path.join(WORKSPACE, "SW-DLT-ENV", "bin", "python")
    PIP_PACKAGES = (
        "chardet", "requests", "certifi", "mutagen",
        "yt-dlp", "yt-dlp-ejs", "yt-dlp-apple-webkit-jsi", "gallery-dl",
    )


def extend_ytdlp_sys_path():
    """Match venv and a-Shell user site-packages (see net00-1/SW-DLT#141 / PR #145)."""
    py_version = f"python{sys.version_info.major}.{sys.version_info.minor}"
    home = os.environ["HOME"]
    for site_dir in (
        os.path.join(home, "Documents", "SW-DLT", "SW-DLT-ENV", "lib", py_version, "site-packages"),
        os.path.join(home, "Library", "lib", py_version, "site-packages"),
    ):
        if os.path.isdir(site_dir) and site_dir not in sys.path:
            sys.path.append(site_dir)


def load_yt_dlp():
    """Import yt-dlp from the SW-DLT venv or a-Shell user site; pip into venv if needed."""
    extend_ytdlp_sys_path()
    try:
        return __import__("yt_dlp")
    except ImportError:
        pass
    pip = Consts.VENV_PYTHON if os.path.isfile(Consts.VENV_PYTHON) else sys.executable
    subprocess.run(
        [pip, "-m", "pip", "install", *Consts.PIP_PACKAGES,
         "-q", "--disable-pip-version-check", "--upgrade"],
        check=False,
    )
    return __import__("yt_dlp")


def unpack_run_payload(arg_list):
    """Accept RUN||<url>||<mode and options> from a single shell argument (safe for & in URLs)."""
    if not arg_list:
        return arg_list
    head = arg_list[0]
    if isinstance(head, str) and head.startswith("RUN||"):
        payload = head[5:]
        if "||" in payload:
            media_url, mode = payload.rsplit("||", 1)
            return [media_url, mode] + list(arg_list[1:])
    return list(arg_list)


class SW_DLT:

    def __init__(self, file_id, *args):
        # args[0]: media URL to download
        # args[1]: main process to run
        # args[2] (dependent): resolution for video, type for playlist, or range for gallery
        # args[3] (dependent): framerate for video
        # optional: --sponsorblock-remove=cat1,cat2 or --sbjson={...} (JSON map of {category: bool})
        arg_list = unpack_run_payload(list(args))
        if len(arg_list) < 2:
            raise ValueError("Missing required arguments from shortcut (media URL and mode)")
        self.media_url = arg_list[0]
        self.file_id = file_id
        self.primary_action = arg_list[1]
        self.date_id = datetime.datetime.today().strftime("%d-%m-%y-%H-%M-%S")
        self.ytdlp_globals = {
            "color": "never",
            "quiet": True,
            "no_warnings": True,
            "noprogress": True,
            "progress_hooks": [show_progress],
            "postprocessor_hooks": [format_processing],
            "cookiesfrombrowser": ("safari",)
        }

        processes = {
            "-v": self.single_video,
            "-a": self.single_audio,
            "-p": self.playlist_download,
            "-g": self.gallery_download
        }
        remaining_args = list(arg_list[2:])
        if isinstance(self.primary_action, str) and " " in self.primary_action and self.primary_action not in processes:
            split_tokens = self.primary_action.split()
            self.primary_action = split_tokens[0]
            remaining_args = split_tokens[1:] + remaining_args
        if self.primary_action not in processes:
            raise ValueError("Missing required arguments from shortcut (media URL and mode)")
        self.run = processes[self.primary_action]
        # SponsorBlock categories
        valid_sb_categories = {
            "sponsor",
            "selfpromo",
            "interaction",
            "intro",
            "outro",
            "preview",
            "filler",
            "music_offtopic",
            "hook"
        }
        self.sponsorblock_remove = []
        self.sb_source_raw = ""
        # Allow sponsorblock config via --sbjson or --sponsorblock-remove
        sb_json = None
        cleaned_args = []
        for token in remaining_args:
            if isinstance(token, str) and token.startswith("--sbjson="):
                sb_json = token.split("=", 1)[1]
                print(f"{Consts.CGREEN}Raw SB JSON arg: {sb_json}{Consts.ENDL}")
                continue
            elif isinstance(token, str) and token.startswith("--sponsorblock-remove="):
                csv = token.split("=", 1)[1]
                categories = [
                    cat.strip().lower()
                    for cat in csv.replace(" ", "").split(",")
                    if cat and cat.lower() != "none"
                ]
                self.sponsorblock_remove.extend(
                    cat for cat in categories if cat in valid_sb_categories
                )
                continue
            cleaned_args.append(token)

        remaining_args = cleaned_args

        if sb_json:
            self.sponsorblock_remove.extend(
                self.parse_sb_json(sb_json, valid_sb_categories)
            )


        self.video_res = ""
        self.video_fps = ""
        self.playlist_type = ""
        self.gallery_range = ""

        self.iphone_playback_optimize = False
        if self.primary_action == "-v" and remaining_args:
            self.video_res = remaining_args.pop(0)
            if self.video_res != "-d" and remaining_args:
                self.video_fps = remaining_args.pop(0)
            self.iphone_playback_optimize = (
                self.video_res == "720" and self.video_fps == "30"
            )
        elif self.primary_action == "-p" and remaining_args:
            self.playlist_type = remaining_args.pop(0)
        elif self.primary_action == "-g" and remaining_args:
            self.gallery_range = remaining_args.pop(0).replace('"','').replace("'","")

    def _apply_sponsorblock(self, dl_options):
        """Inject SponsorBlock settings and ensure PP ordering matches working verifier."""
        if not self.sponsorblock_remove:
            return dl_options

        dl_options["sponsorblock_remove"] = self.sponsorblock_remove
        existing_pps = list(dl_options.get("postprocessors", []))
        sb_pp = {"key": "SponsorBlock", "categories": self.sponsorblock_remove}
        mod_pp = {"key": "ModifyChapters", "remove_sponsor_segments": self.sponsorblock_remove}
        # Run SB first, then ModifyChapters, then any existing PPs; keep remux optional
        pp_list = [sb_pp, mod_pp] + existing_pps
        dl_options["postprocessors"] = pp_list
        return dl_options

    @staticmethod
    def parse_sb_json(sb_json, valid_sb_categories):
        parsed = []
        cleaned = sb_json.strip()
        # Strip outer quotes the shortcut might add
        if (cleaned.startswith('"') and cleaned.endswith('"')) or (cleaned.startswith("'") and cleaned.endswith("'")):
            cleaned = cleaned[1:-1].strip()
        if cleaned.startswith("(") and cleaned.endswith(")"):
            cleaned = cleaned[1:-1]
        replacements = {
            "Yes": "true",
            "yes": "true",
            "No": "false",
            "no": "false",
            "True": "true",
            "False": "false"
        }
        for needle, repl in replacements.items():
            cleaned = cleaned.replace(needle, repl)
        cleaned = cleaned.replace("'", '"')
        if not cleaned.startswith("{"):
            cleaned = "{" + cleaned
        if not cleaned.endswith("}"):
            cleaned = cleaned + "}"
        try:
            cfg = json.loads(cleaned)
            for cat, enabled in cfg.items():
                cat = str(cat).strip().lower()
                if isinstance(enabled, str):
                    enabled = enabled.lower() in {"true", "yes", "1", "on"}
                if enabled is None or enabled == "":
                    enabled = True
                if enabled and cat in valid_sb_categories:
                    parsed.append(cat)
            return parsed
        except Exception:
            pass

        cleaned = cleaned.strip("{}")
        for part in cleaned.split(","):
            if ":" not in part:
                continue
            key, val = part.split(":", 1)
            cat = key.strip().strip('"{} ').lower()
            flag = val.strip().strip('"{} ')
            if flag == "":
                flag = "true"
            if flag.lower() in {"true", "yes", "1", "on"} and cat in valid_sb_categories:
                parsed.append(cat)
        return parsed

    @staticmethod
    def update_check():
        current_time = datetime.datetime.today()
        show_progress("util", 0, 2)
        if not os.path.exists(f"{os.environ['HOME']}/Library/Cookies/Cookies.binarycookies"):
            cookie_expiration = current_time.replace(year=current_time.year + 1).strftime('%a, %-d %b %Y %H:%M:%S UTC')
            set_cookie = f"echo 'document.cookie = \"installed=1; expires={cookie_expiration}; sameSite=Lax\";' | jsi"
            subprocess.run(set_cookie)

        #We need to wait for delay in jsi command
        while not os.path.exists(f"{os.environ['HOME']}/Library/Cookies/Cookies.binarycookies"):
            subprocess.run("sleep 1")
        
        show_progress("util", 1, 2)

        ts_path = os.path.join(Consts.WORKSPACE, "shortcut_update_ts.txt")
        if not os.path.isfile(ts_path):
            os.makedirs(Consts.WORKSPACE, exist_ok=True)
            with open(ts_path, "w") as ts_file:
                ts_file.write("0")

        with open(ts_path, "r") as ts_file:
            last_check = int(ts_file.read().strip() or "0")

        pip = Consts.VENV_PYTHON if os.path.isfile(Consts.VENV_PYTHON) else sys.executable
        if int(current_time.timestamp()) - last_check < 600:
            subprocess.run(
                [pip, "-m", "pip", "install", *Consts.PIP_PACKAGES,
                 "-q", "--disable-pip-version-check", "--upgrade"],
                check=False,
            )
            # yt-dlp is reloaded here to avoid issues after updates
            importlib.reload(yt_dlp)
        
        show_progress("util", 2, 2)

    def single_video(self):
        default_format = "best/bestvideo+bestaudio"
        custom_format = ""\
            "bestvideo[height={0}][fps<={1}]+bestaudio/"\
            "best[height={0}][fps<={1}]/"\
            "bestvideo[height<={0}][fps<={1}]+bestaudio/"\
            "best[height<={0}][fps<={1}]"\
            "best[height={0}]".format(self.video_res, self.video_fps)

        dl_options = {
            "format": default_format if self.video_res == "-d" else custom_format,
            "noplaylist": True,
            "playlist_items": "1-1",
            "outtmpl": f'{self.file_id}.%(ext)s',
            "format_sort": ["res", "ext:mp4:m4a", "codec:avc:m4a"],
            **self.ytdlp_globals
        }

        dl_options = self._apply_sponsorblock(dl_options)
        if self.iphone_playback_optimize:
            dl_options = self._apply_iphone_video_options(dl_options)

        try:
            # Returns shortcuts redirect URL with downloaded file data, any exception is re-thrown
            return self.single_download(dl_options)

        except (yt_dlp.utils.DownloadError, OSError) as ex:
            raise Exception(ex.args[0])

    @staticmethod
    def _apply_iphone_video_options(dl_options):
        dl_options["merge_output_format"] = "mp4"
        dl_options["format_sort"] = [
            "res:720", "fps:30", "ext:mp4:m4a", "codec:avc:h264", "codec:m4a",
        ]
        postprocessors = list(dl_options.get("postprocessors", []))
        postprocessors.append({
            "key": "FFmpegVideoConvertor",
            "preferedformat": "mp4",
        })
        dl_options["postprocessors"] = postprocessors
        dl_options.setdefault("postprocessor_args", {})["FFmpegVideoConvertor"] = [
            "-c:v", "libx264", "-crf", "23", "-preset", "fast",
            "-vf", (
                "scale='min(1280,iw)':min(720\\,ih):"
                "force_original_aspect_ratio=decrease,fps=min(30\\,source_fps)"
            ),
            "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "160k",
            "-movflags", "+faststart",
        ]
        return dl_options

    def single_audio(self):
        dl_options = {
            "format": "bestaudio[ext*=4]/bestaudio[ext=mp3]/best[ext=mp4]/best",
            "noplaylist": True,
            "playlist_items": "1-1",
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "m4a",
                "preferredquality": "192",
            }],
            "outtmpl": f'{self.file_id}.%(ext)s',
            **self.ytdlp_globals
        }

        dl_options = self._apply_sponsorblock(dl_options)

        try:
            # Returns shortcuts redirect URL with downloaded file data, any exception is re-thrown
            return self.single_download(dl_options)

        except (yt_dlp.utils.DownloadError, OSError) as ex:
            raise Exception(ex.args[0])

    def single_download(self, dl_options):
        # Uses yt-dlp to download single video or audio items
        with yt_dlp.YoutubeDL(dl_options) as vid_obj:
            meta_data = vid_obj.extract_info(self.media_url, download=False)
            vid_title = meta_data.get("title", self.date_id)
            vid_obj.download([self.media_url])

        for file in os.listdir():
            if file.startswith(self.file_id):
                output = {
                    "output_code": "success",
                    "file_name": os.path.abspath(file),
                    "file_title": vid_title
                }
                return f'shortcuts://run-shortcut?name=SW-DLT&input=text&text={urllib.parse.quote(json.dumps(output))}'
        # If for some reason the above doesn't find the downloaded file, we raise generic Exception
        raise Exception(Consts.DERROR)

    def gallery_download(self):
        try:
            # Creating temp folder to store media
            os.makedirs(self.file_id, exist_ok=True)
            dl_cmd = "gallery-dl {0} --range \"{1}\" --directory {2} --cookies-from-browser safari".format(
                self.media_url, self.gallery_range, self.file_id)
                
            with subprocess.Popen(dl_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=1, universal_newlines=True) as gdl:
                for entry in gdl.stdout:
                    show_progress("manual", 1, 1)        
                
            files = os.listdir(self.file_id)
            # No files returned, raises Exception
            if len(files) == 0:
                raise OSError()

            # Single item, directly outputs the item
            elif len(files) < 2:
                file = "{0}/{1}".format(self.file_id, files[0])
                output = {
                    "output_code": "success",
                    "file_name": os.path.abspath(file),
                    "file_title": self.date_id
                }

            # Mutiple items, zips temp folder and returns it
            else:
                shutil.make_archive(self.file_id, "zip", self.file_id)
                output = {
                    "output_code": "success",
                    "file_name": os.path.abspath(self.file_id + ".zip"),
                    "file_title": self.date_id
                }

            return f'shortcuts://run-shortcut?name=SW-DLT&input=text&text={urllib.parse.quote(json.dumps(output))}'
        except subprocess.CalledProcessError as ex:
            clean_stderr = ex.output.decode("utf-8").rstrip()
            raise Exception(clean_stderr)
        except (AttributeError, OSError) as ex2:
            raise Exception(Consts.DERROR_EXC)
            
    def playlist_download(self):
        dl_options = {
            "format": "best" if self.playlist_type == "-v" else "bestaudio[ext*=4]/bestaudio[ext=mp3]/best[ext=mp4]/best",
            "postprocessors": [] if self.playlist_type == "-v" else [{"key": "FFmpegExtractAudio", "preferredcodec": "m4a"}],
            "outtmpl": f'{self.file_id}/%(title)s.%(ext)s',
            "format_sort": ["+codec:avc:m4a"],
            **self.ytdlp_globals
        }

        dl_options = self._apply_sponsorblock(dl_options)

        try:
            with yt_dlp.YoutubeDL(dl_options) as pl_obj:
                meta_data = pl_obj.extract_info(self.media_url, download=False)
                pl_title = meta_data.get("title", self.date_id)
                pl_obj.download([self.media_url])

            shutil.make_archive(self.file_id, "zip", self.file_id)
            shutil.rmtree(self.file_id, True)
            output = {
                "output_code": "success",
                "file_name": os.path.abspath(self.file_id + ".zip"),
                "file_title": pl_title
            }
            return f'shortcuts://run-shortcut?name=SW-DLT&input=text&text={urllib.parse.quote(json.dumps(output))}'

        except (yt_dlp.utils.DownloadError, OSError) as ex:
            raise Exception(ex.args[0])


def show_progress(data_stream, curr=0, total=0):
    # data_stream type of data received, can be manual (for gallery-dl downloads), util (for utility processes)
    # it can also be yt-dlp download data streams
    if data_stream == "manual":
        if curr != total:
            print(
                f'\rDownloading: {Consts.CYELLOW}{curr/total:.1%}{Consts.ENDL}', end="")
            return
        print(f'\x1b[1K\r{Consts.CGREEN}Downloaded{Consts.ENDL}')
    elif data_stream == "util":
        print(
            f'\rLoading: {Consts.CYELLOW}{curr/total:.1%}{Consts.ENDL}', end="")
        return
    else:
        if data_stream["status"] == "downloading":
            print(
                f"\rDownloading: {Consts.CYELLOW}{data_stream['_percent_str'].strip()}{Consts.ENDL}", end="")
        elif data_stream["status"] == "finished":
            print(f'\x1b[1K\r{Consts.CGREEN}Downloaded{Consts.ENDL}')
    return


def format_processing(process_stream):
    name = process_stream.get("postprocessor") or ""
    label = f" ({name})" if name else ""
    if process_stream["status"] == "started":
        print(f'\r{Consts.CYELLOW}Processing{label}{Consts.ENDL}', end="")
    elif process_stream["status"] == "finished":
        print(f'\x1b[1K\r{Consts.CGREEN}Processed{label}{Consts.ENDL}')
    return


def main():
    info_msgs = {
        "-v": f'{Consts.CBLUE}Video Download{Consts.ENDL}\n{Consts.CYELLOW}Custom qualities require processing{Consts.ENDL}',
        "-a": f'{Consts.CBLUE}Audio Download{Consts.ENDL}\n{Consts.CYELLOW}Sometimes audio processing is needed{Consts.ENDL}',
        "-p": f'{Consts.CBLUE}Playlist Download{Consts.ENDL}\n{Consts.CYELLOW}Process time depends on playlist length{Consts.ENDL}',
        "-g": f'{Consts.CBLUE}Gallery Download{Consts.ENDL}\n{Consts.CYELLOW}Process time depends on collection length{Consts.ENDL}',
        "-e": f'{Consts.CYELLOW}Deleting All Dependencies{Consts.ENDL}',
        "update_check": f'{Consts.CBLUE}Preparing{Consts.ENDL}\n{Consts.CYELLOW}Checking for Updates{Consts.ENDL}'
    }
    try:
        globals()["yt_dlp"] = load_yt_dlp()
        # Hashes all arguments to generate unique ID
        file_id = "SW_DLT_DL_{}".format(hashlib.md5(
            str(sys.argv).encode("utf-8")).hexdigest()[0:20])

        cli_args = unpack_run_payload(list(sys.argv[1:]))
        sw_dlt_inst = SW_DLT(file_id, *cli_args)
        header = f'{Consts.SBOLD}SW-DLT{Consts.ENDL}'

        # Pre-download check and cleanup
        subprocess.run("clear && hideKeyboard", shell=True)
        
        print(header)
        print(info_msgs["update_check"])            
        sw_dlt_inst.update_check()
        
        # If the same partial file is not found, deletes all leftovers (important)
        for file in os.listdir():
            if file.startswith("SW_DLT_DL_") and not file.startswith(file_id):
                if os.path.isdir(file):
                    shutil.rmtree(file)
                    continue
                os.remove(file)
            elif file.startswith(file_id):
                header = f'{Consts.SBOLD}SW-DLT (Resuming Download){Consts.ENDL}'
        
        subprocess.run("clear")
        print(header)
        print(f"{Consts.CGREEN}yt-dlp version: {yt_dlp.version.__version__}{Consts.ENDL}")
        print(info_msgs.get(sw_dlt_inst.primary_action, info_msgs["-v"]))
        if sw_dlt_inst.sponsorblock_remove:
            sb_label = ", ".join(sw_dlt_inst.sponsorblock_remove)
            print(f"{Consts.CBLUE}SponsorBlock remove: {sb_label}{Consts.ENDL}")
        
        with open('SW_DLT_DL_metadata.json', 'w') as metadata:
            meta_key = sw_dlt_inst.media_url
            meta_val = " ".join(
                str(t)
                for t in cli_args[1:]
                if not (isinstance(t, str) and t.startswith("--sbjson="))
            )
            json.dump({meta_key: meta_val}, metadata)
        
        return sw_dlt_inst.run()

    except Exception as exc_url:
        # All raised exceptions are handled here and send the user back to the shortcut with a message
        if str(exc_url.args[0]) not in [Consts.DERROR_EXC]:
            b64_err = base64.b64encode(exc_url.args[0].encode()).decode()
            UNK_EXC = '{{"output_code":"exception","exc_trace":"{0}"}}'.format(b64_err)
            return f'shortcuts://run-shortcut?name=SW-DLT&input=text&text={urllib.parse.quote(UNK_EXC)}'
        return f'shortcuts://run-shortcut?name=SW-DLT&input=text&text={urllib.parse.quote(str(exc_url.args[0]))}'


if __name__ == "__main__":
    subprocess.run("open " + main())
