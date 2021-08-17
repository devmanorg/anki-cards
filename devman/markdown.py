from os.path import dirname, abspath, join
import subprocess
from functools import partial


def render_markdown(stdin_msg: str, script_name='render_md.js'):
    curr_dir = dirname(dirname(abspath(__file__)))
    script_dir = join(curr_dir, 'js-markdown')

    process = subprocess.run(
        ['node', '--no-warnings', join(script_dir, script_name)],
        input=stdin_msg.encode(),
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL
    )

    if process.returncode:
        raise ValueError('Markdown render has problems, check dependencies!')

    return process.stdout.decode()


render_anki_markdown = partial(render_markdown, script_name='render_anki_md.js')


def render_in_bulk(render_function, raw_chunks):
    delimiter = chr(7)  # beep symbol, is supported by JS script
    joined_html = render_function(delimiter.join(raw_chunks))
    return joined_html.split(delimiter)
