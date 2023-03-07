# whisperGUI
A Graphical User Interface (GUI) for audio/video file transcription powered by openai whisper.

## Developer Setup

The video tutorial (Windows) that I initially followed to get set up for whisper on the command line (where the ffmpeg and whisper terminal commands come from) is at https://www.youtube.com/watch?v=msj3wuYf3d8.

### Python
This application is built using python 3.10. Other versions of python may or may not work with the project.

Install `python`. A good guide at https://realpython.com/installing-python/.
* Remember to install your desired version of python, it's corresponding pip, and venv.

Install `python` version X on Linux
1.	Start by updating the packages list and installing the prerequisites:
    ```bash
    sudo apt update
    sudo apt install software-properties-common
    ```
2.	Next, add the deadsnakes PPA to your sources list:
    ```bash
    sudo add-apt-repository ppa:deadsnakes/ppa
    ```
    When prompted press Enter to continue:
    * Press [ENTER] to continue or Ctrl-c to cancel adding it.
3.	Once the repository is enabled, install Python X with:
    ```bash
    sudo apt install pythonX
    ```
4.	At this point, Python X is installed on your Ubuntu system and ready to be used. You can verify it by typing:
    ```bash
    pythonX—versionCopy
    ```
5.	Install the other needed packages
    ```bash
    sudo apt install pythonX-dev
    sudo apt install pythonX-minimal
    sudo apt install pythonX-distutils
    sudo apt install pythonX-venv
    ```
6.	Update `pip` for pythonX
    ```bash
    pythonX -m pip install --upgrade pip
    ```

### Virtual Environment
Create a virtual environment (`venv` will be used throughout this document).
* Example using `venv`
    ```bash
    python3 -m venv venv
    ```

Activate a virtual environment (or use an alias for the cmd)
```bash
deactivate &> /dev/null; source ./venv/bin/activate
```
Note: convention is to call the virtual environment directory `venv` and the alias assumes you follow that convention.

(Optional) Make a permanent alias for activating/deactivating the virtual environment. Copy these lines into your `.bashrc` file.
```bash
alias ae='deactivate &> /dev/null; source ./venv/bin/activate'
alias de='deactivate'
```
These aliases only work if you create virtual environment directories that are always called `venv` in each project folder.
These aliases must be used in a project directory that contains a `venv` virtual environment directory.

### FFMPEG
Install `ffmpeg` (if NOT using a ffmpeg static binary)
```bash
sudo apt update && sudo apt install ffmpeg
```
* Installing ffmpeg is not needed. We use a static binary for ffmpeg to avoid installing it.

### Installing python packages
Update `pip` if you haven't already done so.
```bash
python3 -m pip install --upgrade pip
```

Install packages using the `requirements.txt` file with whichever tool you prefer.
* Example using `pip-tools`
    ```bash
    pip3 install pip-tools
    pip-sync
    ```

If you see installation errors during the pip install command for `whisper`, install `rust` with:
```bash
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
```

Then try to install `whisper` again
```bash
pip3 install git+https://github.com/openai/whisper.git
```

## ffmpeg binary sources

ffmpeg v5 binaries are currently being used.

MacOS (Intel):

https://evermeet.cx/pub/ffmpeg/ffmpeg-5.0.zip

Windows:

https://www.gyan.dev/ffmpeg/builds/packages/ffmpeg-5.0.1-full_build-shared.7z

Linux:

https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz
https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-i686-static.tar.xz
https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-arm64-static.tar.xz
https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-armhf-static.tar.xz
https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-armel-static.tar.xz

## How to install CUDA support for using GPU when doing transcription of audio (Windows only)

* CUDA support comes with Linux `whisper` package install of pytorch by default.

Delete existing `Pytorch`
```bash
pip3 uninstall torch
```

Clear the `pip` cache
```bash
pip3 cache purge
```

Install `Pytorch` with CUDA support :
```bash
pip3 install torch torchvision torchaudio --extra-index-url https://download.pytorch.org/whl/cu116
```

## You can use losslesscut to cut a video
https://github.com/mifi/lossless-cut/releases

## Available models and languages

There are five model sizes, four with English-only versions, offering speed and accuracy tradeoffs. Below are the names of the available models and their approximate memory requirements and relative speed.


|  Size  | Parameters | English-only model | Multilingual model | Required VRAM | Relative speed |
|:------:|:----------:|:------------------:|:------------------:|:-------------:|:--------------:|
|  tiny  |    39 M    |     `tiny.en`      |       `tiny`       |     ~1 GB     |      ~32x      |
|  base  |    74 M    |     `base.en`      |       `base`       |     ~1 GB     |      ~16x      |
| small  |   244 M    |     `small.en`     |      `small`       |     ~2 GB     |      ~6x       |
| medium |   769 M    |    `medium.en`     |      `medium`      |     ~5 GB     |      ~2x       |
| large  |   1550 M   |        N/A         |      `large`       |    ~10 GB     |       1x       |

For English-only applications, the `.en` models tend to perform better, especially for the `tiny.en` and `base.en` models. We observed that the difference becomes less significant for the `small.en` and `medium.en` models.

Whisper's performance varies widely depending on the language.

## Command line usage of whisper

whisper converts your input with ffmpeg (effectively the console command `ffmpeg -i \<recording> -ar 16000 -ac 1 -c:a pcm_s16le \<output>.wav`) and pre-processes it before doing any speech recognition.

You can just give it your video files, except when that command wouldn't work (like if you have multiple audio languages and don't want the default track).

In such a case, you would need to use `ffmpeg` to convert the video file to an audio/video file with the desired audio track. See ffmpeg's documentation for details.

How to extract sound of any video with `ffmpeg`
```bash
ffmpeg -i "test_video.webm" -q:a 0 -map a test_video.mp3
```

Note: `whisper` command line will not work without one of the following:
* Add the file path of the directory for the `ffmpeg` static binary for your operating system to the `PATH` environment variable (basically what `set_env.py` does for the GUI application) .
    * Linux: Add directory for amd64 `ffmpeg` using `.bashrc` file.
        ```bash
        export FFMPEGPATH='~/whisperGUI/ffmpeg/linux/amd64/'
        export PATH=$PATH:$FFMPEGPATH
        ```
        Or in 1 line without a `FFMPEGPATH` environment variable.
        ```bash
        export PATH=$PATH:~/whisperGUI/ffmpeg/linux/amd64/
        ```
    * Windows: Add directory for windows `ffmpeg` using powershell profile.
        ```bash
        $env:Path += [IO.Path]::PathSeparator + 'C:\path\to\whisperGUI\ffmpeg\windows'
        ```
        * If you don't know how to set up a powershell profile, a decent guide is at https://lazyadmin.nl/powershell/powershell-profile/. I used the Current user – Current host profile.
    * Note: Windows uses `;` while Linux uses `:` as the path separator character.
* Install `ffmpeg`.
    * Not recommended if building a standalone executable using a tool like `pyinstaller`. Your python project may appear to work but actually use an installed `ffmpeg` instead of a static binary `ffmpeg`. This would lead to `ffmpeg` issues when running the standalone executable.

How to transcribe an English video
```bash
whisper "C:\speech to text\test_video.mp4" --language en --model base.en --device cpu --task transcribe
```

How to transcribe an English video with CUDA support
```bash
whisper "C:\speech to text\test_video.mp4" --language en --model base.en --device cuda --task transcribe
```

How to transcribe a Turkish video
```bash
whisper "C:\speech to text\test_video.mp4" --language tr --model base.en --device cpu --task transcribe
```

How to transcribe a Turkish video with translation
```bash
whisper "C:\speech to text\test.mp4" --language tr --model small --device cuda -o "C:\speech to text" --task translate
```

How to transcribe a Chinese video with CUDA support that outputs to an 'outputs' subdirectory
```bash
whisper "C:\speech to text\test_video.mp4" --language Chinese --model large --device cuda --task transcribe -o outputs
```

## Deploying using Pyinstaller
If needed, install packages from the `requirements.txt` file (for example, using a fresh VM).
```bash
pip3 install -r requirements.txt
```

Install additional packages
```bash
python -m pip install --upgrade pip
pip install six
pip install pyinstaller
pip install importlib_metadata
pip install wheel
```

Build with `pyinstaller`

* Run the `pyinstaller` command in your project directory (the one with `whisperGUI.py`)

Windows
```bash
pyinstaller -D -w --uac-admin --python-option="u" --paths="./venv/Lib/site-packages" --hidden-import=pytorch --collect-data torch --copy-metadata torch --copy-metadata tqdm --copy-metadata regex --copy-metadata requests --copy-metadata packaging --copy-metadata filelock --copy-metadata numpy --copy-metadata tokenizers --copy-metadata importlib_metadata --add-binary="ffmpeg/windows;ffmpeg/windows" --collect-data "whisper" --runtime-hook=set_env.py whisperGUI.py --noconfirm
```
Linux
```bash
pyinstaller -D -w --python-option="u" --paths="./venv/lib/python3.10/site-packages/" --hidden-import=pytorch --collect-data torch --copy-metadata torch --copy-metadata tqdm --copy-metadata regex --copy-metadata requests --copy-metadata packaging --copy-metadata filelock --copy-metadata numpy --copy-metadata tokenizers --copy-metadata importlib_metadata --add-binary="ffmpeg/linux:ffmpeg/linux" --collect-data "whisper" --runtime-hook=set_env.py whisperGUI.py --noconfirm
```
* Use `/` in path strings to avoid needing to use `\\`
* Use `-D` / `--onedir` instead of `-F` / `--onefile` option for creating a directory with the exe instead of a single exe file.
* For `--paths` option, use the path to your `site-packages` directory. It will differ depending on your operating system and where you installed python packages (in a virtual environment or globally).
    * The above OS-specific commands use a `site-packages` directory in a virtual environment subdirectory called `venv` with python 3.10 in the project directory.
* A static binary for `ffmpeg` is used so we must include it with `--add-binary`.
* Our runtime hook enables the use of `ffmpeg` on the command line which will run our included static ffmpeg binary.
* Use `--noconfirm` to automatically overwrite the build and dist directories.
* Use python 3.8 or lower due to issue with pyinstaller and python
    ```
    This is the first version of Python to default to the 64-bit installer on Windows. The installer now also actively disallows installation on Windows 7. Python 3.9 is incompatible with this unsupported version of Windows.
    ```

## Building compressed files
### Windows
Use a tool like 7-Zip with high compression settings.
![image](https://user-images.githubusercontent.com/21352182/223277748-67012d17-3540-43cd-8d85-dddd74957181.png)

### Linux
Navigate to the project directory's dist folder `whisperGUI/dist` (it contains the `whisperGUI` folder created by the `pyinstaller` command) and then run the following.
```bash
tar -cf - whisperGUI/ | xz -9 --threads=0 - > whisperGUI_Linux.tar.xz
```
* -9 is highest compression level. use -9e for xz if you need even more compression (extreme) at the cost of higher (~2x) compression time.
* Use -T0 or --threads=0 to makes xz use as many threads as there are CPU cores on the system


## Models
You can directly download all of the models if you need them.

```JSON
_MODELS = {
    "tiny.en": "https://openaipublic.azureedge.net/main/whisper/models/d3dd57d32accea0b295c96e26691aa14d8822fac7d9d27d5dc00b4ca2826dd03/tiny.en.pt",
    "tiny": "https://openaipublic.azureedge.net/main/whisper/models/65147644a518d12f04e32d6f3b26facc3f8dd46e5390956a9424a650c0ce22b9/tiny.pt",
    "base.en": "https://openaipublic.azureedge.net/main/whisper/models/25a8566e1d0c1e2231d1c762132cd20e0f96a85d16145c3a00adf5d1ac670ead/base.en.pt",
    "base": "https://openaipublic.azureedge.net/main/whisper/models/ed3a0b6b1c0edf879ad9b11b1af5a0e6ab5db9205f891f668f8b0e6c6326e34e/base.pt",
    "small.en": "https://openaipublic.azureedge.net/main/whisper/models/f953ad0fd29cacd07d5a9eda5624af0f6bcf2258be67c92b79389873d91e0872/small.en.pt",
    "small": "https://openaipublic.azureedge.net/main/whisper/models/9ecf779972d90ba49c06d968637d720dd632c55bbf19d441fb42bf17a411e794/small.pt",
    "medium.en": "https://openaipublic.azureedge.net/main/whisper/models/d7440d1dc186f76616474e0ff0b3b6b879abc9d1a4926b7adfa41db2d497ab4f/medium.en.pt",
    "medium": "https://openaipublic.azureedge.net/main/whisper/models/345ae4da62f9b3d59415adc60127b97c714f32e89e936602e85993674d08dcb1/medium.pt",
    "large": "https://openaipublic.azureedge.net/main/whisper/models/e4b87e7e0bf463eb8e6956e646f1e277e901512310def2c24bf0e11bd3c28e9a/large.pt",
}
```

* Above is from `.../site-packages/whisper/__init__.py` and may change.
* Tip: To avoid the GUI needing to download a model when using it for the first time, download the models and place them all in the directory that whisper auto downloads models into.
* Models auto downloaded by whisper will be in `~/.cache/whisper/` on Linux and `C:\Users\<username>\.cache\whisper\` on Windows.

## Common development issues
Running process X results in the program getting killed with the message 'Killed'.
* The process is being killed by the OOM killer (Out Of Memory Killer), which is a process of the operating system whose job it is to kill jobs that are taking up too much memory before they crash your machine. This is a good thing. Without it, your machine would simply become unresponsive.
* So, you need to figure out why your python script is taking up so much memory, and try to make it so that it uses less. The only other alternative is to try and get more swap, or more RAM.
* Fix (VSCode only): Open another workspace, switch back to your original workspace, and then try running the process again.

A `pip` package install results in the program getting killed with the message 'Killed'
* add the `--no-cache-dir` option when using `pip`, i.e.,

    ```bash
    pip3 install X --no-cache-dir
    ```

PermissionError: [Errno 13] Permission denied: 'ffmpeg'
* On Linux, you need to give executable permissions to the `ffmpeg` file.
    * Ex. `ffmpeg` file for amd64
        ```bash
        chmod +x ~/whisperGUI/ffmpeg/linux/amd64/ffmpeg
        ```
        * The above command assumes the whisperGUI repo is in the user's home directory.

whisper (either through cmd line or whisper python package) uses CPU when a CUDA GPU is installed and no option to use CPU is given.
* Restart your computer. Sometimes the torch detects the GPU as unavailable for some reason.

pyinstaller builds successfully but running the executable results in an error in `transformers\utils\logging.py`'s `_configure_library_root_logger` function with the message `Failed to execute script 'whisperGUI' due to unhandled exception: 'NoneType' object has no attribute 'flush'`.
![image](https://user-images.githubusercontent.com/21352182/223229439-f6c99e30-df90-47b2-95cc-f484ab825545.png)
1. Open the following file in the `site-packages` directory `.\transformers\utils\logging.py`.
    * The `site-packages` directory path can be found by running the following in the terminal.
        ```bash
        python -c "from distutils.sysconfig import get_python_lib; print(get_python_lib())"
        ```
2. Go to the function definition for `_configure_library_root_logger` and replace the following code inside of it.

    Original Code
    ```python
    _default_handler = logging.StreamHandler()  # Set sys.stderr as stream.
    _default_handler.flush = sys.stderr.flush
    ```
    ![image](https://user-images.githubusercontent.com/21352182/223228785-f0d81b1b-dbc5-46a8-984f-a57c8e1f92ea.png)
    New Code
    ```python
    _default_handler = sys.stderr
    ```
    ![image](https://user-images.githubusercontent.com/21352182/223228931-b3ecce09-d6f2-4797-82d9-e73e758749e1.png)
3. Save the `logging.py` file and rebuild using pyinstaller.

## Credits
This GUI would not be possible without openai whisper. Read more about it at https://openai.com/blog/whisper/.

Icon - <a href="https://www.flaticon.com/free-icons/text-to-speech" title="text to speech icons">Text to speech icons created by Freepik - Flaticon</a>
