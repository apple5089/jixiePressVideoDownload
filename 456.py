import requests
from bs4 import BeautifulSoup
import re
import os
import time
import random
from datetime import datetime


class MediaDownloader:
    def __init__(self, base_url="http://qr.cmpedu.com/CmpBookResource/show_resource.do?id="):
        self.base_url = base_url
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Connection': 'keep-alive',
            'Referer': 'http://qr.cmpedu.com/'
        }
        self.session = requests.Session()
        self.success_list = []
        self.failed_list = []
        self.no_media_list = []

    def _fix_url(self, url):
        """修复转义的URL"""
        if not url:
            return None
        url = url.strip('"\'')
        url = url.replace(r'\/', '/')
        url = url.replace(r'\\/', '/')
        return url.strip()

    def _extract_resource_name(self, soup):
        """精确提取资源名称"""
        for p in soup.find_all('p'):
            text = p.get_text().strip()
            if '资源名称：' in text or '资源名称:' in text:
                name = re.sub(r'^资源名称[：:]\s*', '', text).strip()
                if name:
                    print(f"📋 资源名称: {name}")
                    return name

        video_title = soup.find('p', class_='video_title')
        if video_title:
            name = video_title.get_text().strip()
            if name:
                print(f"📋 使用标题: {name}")
                return name

        title = soup.find('title')
        if title and title.string:
            title_text = title.string.strip()
            if title_text and title_text != '资源详情':
                print(f"📋 使用页面title: {title_text}")
                return title_text

        return None

    def _clean_filename(self, name):
        """清理文件名"""
        if not name:
            return "unknown"

        name = re.sub(r'[\\/:*?"<>|\n\r\t]', '_', name)
        name = re.sub(r'\s+', ' ', name).strip()
        name = name.strip('._- ')

        if len(name) > 120:
            name = name[:120]

        return name if name else "unknown"

    def _extract_image_url(self, soup, html_text):
        """提取图片URL"""
        img_tag = soup.find('img', id='image')
        if img_tag:
            src = img_tag.get('src') or img_tag.get('data-original')
            if src:
                url = self._fix_url(src)
                if url and any(ext in url.lower() for ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp']):
                    print(f"✅ img#image")
                    return url

        for img in soup.find_all('img'):
            src = img.get('src') or img.get('data-original') or img.get('data-src')
            if src:
                url = self._fix_url(src)
                if url and any(ext in url.lower() for ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp']):
                    if 'icon' not in url.lower() and 'logo' not in url.lower():
                        print(f"✅ img标签")
                        return url

        pattern = r'https?:\\?/\\?/[^\s"\'<>]+\.(?:jpg|jpeg|png|gif|bmp)'
        matches = re.findall(pattern, html_text, re.IGNORECASE)
        if matches:
            url = self._fix_url(matches[0])
            if url:
                print(f"✅ 文本搜索")
                return url

        return None

    def _extract_video_url(self, soup, html_text):
        """提取视频URL"""
        video_tag = soup.find('video')
        if video_tag and video_tag.get('src'):
            url = self._fix_url(video_tag.get('src'))
            if url:
                print(f"✅ video.src")
                return url

        source_tag = soup.find('source')
        if source_tag and source_tag.get('src'):
            url = self._fix_url(source_tag.get('src'))
            if url:
                print(f"✅ source.src")
                return url

        pattern1 = r'source\s*:\s*["\']([^"\']+\.mp4)["\']'
        matches = re.findall(pattern1, html_text, re.IGNORECASE)
        if matches:
            url = self._fix_url(matches[0])
            if url:
                print(f"✅ JS source")
                return url

        pattern2 = r'(?:src|url)\s*:\s*["\']([^"\']+\.mp4)["\']'
        matches = re.findall(pattern2, html_text, re.IGNORECASE)
        if matches:
            url = self._fix_url(matches[0])
            if url:
                print(f"✅ JS src/url")
                return url

        pattern3 = r'https?:\\?/\\?/[^\s"\'<>]+\.mp4'
        matches = re.findall(pattern3, html_text)
        if matches:
            url = self._fix_url(matches[0])
            if url:
                print(f"✅ 转义链接")
                return url

        pattern4 = r'https?://[^\s"\'<>]+\.mp4'
        matches = re.findall(pattern4, html_text)
        if matches:
            url = self._fix_url(matches[0])
            if url:
                print(f"✅ 标准链接")
                return url

        return None

    def download_single_media(self, media_id, save_debug=False):
        """下载单个资源（视频或图片）"""
        url = f"{self.base_url}{media_id}"

        try:
            print(f"\n{'=' * 60}")
            print(f"[{datetime.now().strftime('%H:%M:%S')}] ID: {media_id}")

            response = self.session.get(url, headers=self.headers, timeout=30)
            response.encoding = 'utf-8'

            if response.status_code != 200:
                print(f"❌ 页面错误({response.status_code})")
                return False

            if save_debug:
                with open(f"debug_{media_id}.html", 'w', encoding='utf-8') as f:
                    f.write(response.text)

            soup = BeautifulSoup(response.text, 'html.parser')

            resource_name = self._extract_resource_name(soup)
            if not resource_name:
                resource_name = f"resource_{media_id}"
                print(f"⚠️  使用默认名称")

            clean_name = self._clean_filename(resource_name)

            video_url = self._extract_video_url(soup, response.text)
            image_url = self._extract_image_url(soup, response.text)

            if not video_url and not image_url:
                print(f"⚠️  无视频/图片")
                self.no_media_list.append(media_id)
                return False

            download_success = False

            if video_url:
                print(f"🎬 视频: {video_url}")
                video_path = f"{media_id}_{clean_name}.mp4"

                try:
                    test_file = video_path + '.tmp'
                    with open(test_file, 'w') as f:
                        pass
                    os.remove(test_file)
                except:
                    print(f"⚠️  文件名问题，简化")
                    video_path = f"{media_id}.mp4"

                if os.path.exists(video_path):
                    size_mb = os.path.getsize(video_path) / (1024 * 1024)
                    print(f"⏭️  视频已存在({size_mb:.1f}MB)")
                    download_success = True
                else:
                    print(f"📥 保存视频: {video_path}")
                    if self._download_file(video_url, video_path):
                        print(f"✅ 视频完成")
                        download_success = True
                    else:
                        print(f"❌ 视频失败")

            if image_url:
                print(f"🖼️  图片: {image_url}")

                img_ext = os.path.splitext(image_url.split('?')[0])[-1]
                if not img_ext or img_ext not in ['.jpg', '.jpeg', '.png', '.gif', '.bmp']:
                    img_ext = '.jpg'

                image_path = f"{media_id}_{clean_name}{img_ext}"

                try:
                    test_file = image_path + '.tmp'
                    with open(test_file, 'w') as f:
                        pass
                    os.remove(test_file)
                except:
                    print(f"⚠️  文件名问题，简化")
                    image_path = f"{media_id}{img_ext}"

                if os.path.exists(image_path):
                    size_kb = os.path.getsize(image_path) / 1024
                    print(f"⏭️  图片已存在({size_kb:.1f}KB)")
                    download_success = True
                else:
                    print(f"📥 保存图片: {image_path}")
                    if self._download_file(image_url, image_path, is_image=True):
                        print(f"✅ 图片完成")
                        download_success = True
                    else:
                        print(f"❌ 图片失败")

            if download_success:
                self.success_list.append({
                    'id': media_id,
                    'name': clean_name,
                    'video_url': video_url,
                    'image_url': image_url
                })
                return True
            else:
                return False

        except Exception as e:
            print(f"❌ 错误: {str(e)}")
            return False

    def _download_file(self, url, file_path, is_image=False):
        """下载文件"""
        try:
            response = self.session.get(url, headers=self.headers, stream=True, timeout=60)

            if response.status_code != 200:
                print(f"❌ 下载失败({response.status_code})")
                return False

            total_size = int(response.headers.get('content-length', 0))

            with open(file_path, 'wb') as f:
                if is_image and total_size < 10 * 1024 * 1024:
                    f.write(response.content)
                    print(f"💾 {total_size / 1024:.1f}KB")
                else:
                    downloaded = 0
                    start_time = time.time()
                    last_print = 0

                    for chunk in response.iter_content(chunk_size=1024 * 1024):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)

                            current = time.time()
                            if current - last_print >= 0.5:
                                if total_size > 0:
                                    percent = (downloaded / total_size) * 100
                                    mb_down = downloaded / (1024 * 1024)
                                    mb_total = total_size / (1024 * 1024)
                                    elapsed = current - start_time
                                    speed = (downloaded / elapsed / 1024) if elapsed > 0 else 0

                                    print(f"\r⬇️  {percent:.1f}% ({mb_down:.1f}/{mb_total:.1f}MB) {speed:.0f}KB/s",
                                          end='')
                                last_print = current

                    if not is_image:
                        print()

            if total_size > 0:
                actual = os.path.getsize(file_path)
                if actual < total_size * 0.95:
                    print(f"⚠️  文件可能不完整")
                    return False

            return True

        except Exception as e:
            print(f"\n❌ 下载失败: {str(e)}")
            if os.path.exists(file_path):
                os.remove(file_path)
            return False

    def batch_download(self, start_id, end_id, delay_range=(3, 10)):
        """批量下载 - 随机延迟"""
        print(f"\n{'🚀 ' * 30}")
        print(f"批量下载: {start_id} → {end_id} (共 {start_id - end_id + 1} 个)")
        print(f"随机延迟: {delay_range[0]}-{delay_range[1]}秒")
        print(f"{'🚀 ' * 30}\n")

        start_time = time.time()
        current_id = start_id

        while current_id >= end_id:
            success = self.download_single_media(current_id)

            if not success and current_id not in self.no_media_list:
                self.failed_list.append(current_id)

            current_id -= 1

            # 随机延迟
            if current_id >= end_id:
                delay = random.uniform(delay_range[0], delay_range[1])
                print(f"⏳ 等待 {delay:.1f}秒...")
                time.sleep(delay)

        elapsed = time.time() - start_time
        self._print_summary(elapsed)

    def retry_failed(self, delay_range=(3, 8)):
        """重试失败的下载 - 随机延迟"""
        if not self.failed_list:
            print("没有失败的任务")
            return

        print(f"\n🔄 重试 {len(self.failed_list)} 个失败任务\n")

        failed_copy = self.failed_list.copy()
        self.failed_list = []

        for media_id in failed_copy:
            success = self.download_single_media(media_id)
            if not success:
                self.failed_list.append(media_id)

            delay = random.uniform(delay_range[0], delay_range[1])
            print(f"⏳ 等待 {delay:.1f}秒...")
            time.sleep(delay)

        print(f"\n✅ 重试成功: {len(failed_copy) - len(self.failed_list)} 个")

    def _print_summary(self, elapsed_time):
        """统计报告"""
        total = len(self.success_list) + len(self.no_media_list) + len(self.failed_list)

        print(f"\n{'=' * 60}")
        print(f"📊 完成统计")
        print(f"{'=' * 60}")
        print(f"✅ 成功: {len(self.success_list)}")
        print(f"⚠️  无资源: {len(self.no_media_list)}")
        print(f"❌ 失败: {len(self.failed_list)}")
        print(f"📦 总计: {total}")
        print(f"⏱️  耗时: {elapsed_time / 60:.1f} 分钟")
        print(f"{'=' * 60}\n")

    def save_report(self, filename="download_report.txt"):
        """保存下载报告"""
        with open(filename, 'w', encoding='utf-8') as f:
            f.write("媒体下载报告\n")
            f.write("=" * 60 + "\n\n")

            f.write(f"✅ 成功: {len(self.success_list)} 个\n\n")
            for item in self.success_list:
                f.write(f"ID {item['id']}: {item['name']}\n")
                if item.get('video_url'):
                    f.write(f"  视频: {item['video_url']}\n")
                if item.get('image_url'):
                    f.write(f"  图片: {item['image_url']}\n")
                f.write("\n")

            if self.no_media_list:
                f.write(f"\n⚠️  无资源: {len(self.no_media_list)} 个\n")
                f.write(f"{', '.join(map(str, self.no_media_list))}\n")

            if self.failed_list:
                f.write(f"\n❌ 失败: {len(self.failed_list)} 个\n")
                f.write(f"{', '.join(map(str, self.failed_list))}\n")

        print(f"📄 报告已保存: {filename}")


# 使用示例
if __name__ == "__main__":
    downloader = MediaDownloader()

    # 批量下载 - 随机延迟3-10秒
    downloader.batch_download(
        start_id=141150,
        end_id=141077,
        delay_range=(3, 10)
    )

    # 重试失败的
    if downloader.failed_list:
        print("\n重试失败的下载? (y/n): ", end='')
        if input().lower() == 'y':
            downloader.retry_failed(delay_range=(3, 8))

    # 保存报告
    downloader.save_report()
