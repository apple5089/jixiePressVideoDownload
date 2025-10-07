import requests
from bs4 import BeautifulSoup
import re
import os
import time
from datetime import datetime


class VideoDownloader:
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
        self.no_video_list = []

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

        # 方法1: 查找包含"资源名称："的p标签（最精确）
        for p in soup.find_all('p'):
            text = p.get_text().strip()
            if '资源名称：' in text or '资源名称:' in text:
                # 提取冒号后的内容
                name = re.sub(r'^资源名称[：:]\s*', '', text).strip()
                if name:
                    print(f"📋 资源名称: {name}")
                    return name

        # 方法2: 查找video_title类
        video_title = soup.find('p', class_='video_title')
        if video_title:
            name = video_title.get_text().strip()
            if name:
                print(f"📋 使用标题: {name}")
                return name

        # 方法3: title标签
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

        # 移除Windows非法字符
        name = re.sub(r'[\\/:*?"<>|\n\r\t]', '_', name)

        # 合并多余空格
        name = re.sub(r'\s+', ' ', name).strip()

        # 移除前后的特殊字符
        name = name.strip('._- ')

        # 限制长度
        if len(name) > 120:
            name = name[:120]

        return name if name else "unknown"

    def _extract_video_url_advanced(self, soup, html_text):
        """提取视频URL"""

        # 方法1: video标签
        video_tag = soup.find('video')
        if video_tag and video_tag.get('src'):
            url = self._fix_url(video_tag.get('src'))
            if url:
                print(f"✅ video.src")
                return url

        # 方法2: source标签
        source_tag = soup.find('source')
        if source_tag and source_tag.get('src'):
            url = self._fix_url(source_tag.get('src'))
            if url:
                print(f"✅ source.src")
                return url

        # 方法3: JavaScript中的 source: "url"
        pattern1 = r'source\s*:\s*["\']([^"\']+\.mp4)["\']'
        matches = re.findall(pattern1, html_text, re.IGNORECASE)
        if matches:
            url = self._fix_url(matches[0])
            if url:
                print(f"✅ JS source")
                return url

        # 方法4: src/url属性
        pattern2 = r'(?:src|url)\s*:\s*["\']([^"\']+\.mp4)["\']'
        matches = re.findall(pattern2, html_text, re.IGNORECASE)
        if matches:
            url = self._fix_url(matches[0])
            if url:
                print(f"✅ JS src/url")
                return url

        # 方法5: 转义链接
        pattern3 = r'https?:\\?/\\?/[^\s"\'<>]+\.mp4'
        matches = re.findall(pattern3, html_text)
        if matches:
            url = self._fix_url(matches[0])
            if url:
                print(f"✅ 转义链接")
                return url

        # 方法6: 标准链接
        pattern4 = r'https?://[^\s"\'<>]+\.mp4'
        matches = re.findall(pattern4, html_text)
        if matches:
            url = self._fix_url(matches[0])
            if url:
                print(f"✅ 标准链接")
                return url

        return None

    def download_single_video(self, video_id, save_debug=False):
        """下载单个视频"""
        url = f"{self.base_url}{video_id}"

        try:
            print(f"\n{'=' * 60}")
            print(f"[{datetime.now().strftime('%H:%M:%S')}] ID: {video_id}")

            response = self.session.get(url, headers=self.headers, timeout=30)
            response.encoding = 'utf-8'

            if response.status_code != 200:
                print(f"❌ 页面错误({response.status_code})")
                return False

            if save_debug:
                with open(f"debug_{video_id}.html", 'w', encoding='utf-8') as f:
                    f.write(response.text)

            soup = BeautifulSoup(response.text, 'html.parser')

            # 提取视频URL
            video_url = self._extract_video_url_advanced(soup, response.text)

            if not video_url:
                print(f"⚠️  无视频")
                self.no_video_list.append(video_id)
                return False

            print(f"🔗 {video_url}")

            # 提取资源名称
            resource_name = self._extract_resource_name(soup)
            if not resource_name:
                # 从URL提取
                resource_name = video_url.split('/')[-1].replace('.mp4', '')
                print(f"⚠️  使用URL文件名: {resource_name}")

            # 清理文件名
            clean_name = self._clean_filename(resource_name)

            # 生成文件路径
            file_path = f"{video_id}_{clean_name}.mp4"

            # 验证文件名有效性
            try:
                test_file = file_path + '.tmp'
                with open(test_file, 'w') as f:
                    pass
                os.remove(test_file)
            except:
                print(f"⚠️  文件名有问题，使用简化名")
                file_path = f"{video_id}.mp4"

            # 检查已存在
            if os.path.exists(file_path):
                size_mb = os.path.getsize(file_path) / (1024 * 1024)
                print(f"⏭️  已存在({size_mb:.1f}MB)")
                self.success_list.append({
                    'id': video_id,
                    'name': clean_name,
                    'file': file_path,
                    'url': video_url
                })
                return True

            # 下载视频
            print(f"📥 保存为: {file_path}")
            success = self._download_file(video_url, file_path)

            if success:
                self.success_list.append({
                    'id': video_id,
                    'name': clean_name,
                    'file': file_path,
                    'url': video_url
                })
                print(f"✅ 完成")
                return True
            else:
                return False

        except Exception as e:
            print(f"❌ 错误: {str(e)}")
            return False

    def _download_file(self, url, file_path):
        """下载文件"""
        try:
            response = self.session.get(url, headers=self.headers, stream=True, timeout=60)

            if response.status_code != 200:
                print(f"❌ 下载失败({response.status_code})")
                return False

            total_size = int(response.headers.get('content-length', 0))

            with open(file_path, 'wb') as f:
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

                                print(f"\r⬇️  {percent:.1f}% ({mb_down:.1f}/{mb_total:.1f}MB) {speed:.0f}KB/s", end='')
                            last_print = current

            print()

            # 验证完整性
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

    def batch_download(self, start_id, end_id, delay=2):
        """批量下载"""
        print(f"\n{'🚀 ' * 30}")
        print(f"批量下载: {start_id} → {end_id} (共 {start_id - end_id + 1} 个)")
        print(f"间隔: {delay}秒")
        print(f"{'🚀 ' * 30}\n")

        start_time = time.time()
        current_id = start_id

        while current_id >= end_id:
            success = self.download_single_video(current_id)

            if not success and current_id not in self.no_video_list:
                self.failed_list.append(current_id)

            current_id -= 1

            if current_id >= end_id and delay > 0:
                time.sleep(delay)

        elapsed = time.time() - start_time
        self._print_summary(elapsed)

    def retry_failed(self, delay=3):
        """重试失败的下载"""
        if not self.failed_list:
            print("没有失败的任务")
            return

        print(f"\n🔄 重试 {len(self.failed_list)} 个失败任务\n")

        failed_copy = self.failed_list.copy()
        self.failed_list = []

        for video_id in failed_copy:
            success = self.download_single_video(video_id)
            if not success:
                self.failed_list.append(video_id)

            if delay > 0:
                time.sleep(delay)

        print(f"\n✅ 重试成功: {len(failed_copy) - len(self.failed_list)} 个")

    def _print_summary(self, elapsed_time):
        """统计报告"""
        total = len(self.success_list) + len(self.no_video_list) + len(self.failed_list)

        print(f"\n{'=' * 60}")
        print(f"📊 完成统计")
        print(f"{'=' * 60}")
        print(f"✅ 成功: {len(self.success_list)}")
        print(f"⚠️  无视频: {len(self.no_video_list)}")
        print(f"❌ 失败: {len(self.failed_list)}")
        print(f"📦 总计: {total}")
        print(f"⏱️  耗时: {elapsed_time / 60:.1f} 分钟")

        if self.success_list:
            total_size = sum(os.path.getsize(item['file'])
                             for item in self.success_list
                             if os.path.exists(item['file']))
            print(f"💾 总大小: {total_size / (1024 ** 3):.2f} GB")

        if self.no_video_list and len(self.no_video_list) <= 20:
            print(f"\n⚠️  无视频ID: {', '.join(map(str, self.no_video_list))}")

        if self.failed_list:
            print(f"\n❌ 失败ID: {', '.join(map(str, self.failed_list))}")

        print(f"{'=' * 60}\n")

    def save_report(self, filename="download_report.txt"):
        """保存下载报告"""
        with open(filename, 'w', encoding='utf-8') as f:
            f.write("视频下载报告\n")
            f.write("=" * 60 + "\n\n")

            f.write(f"✅ 成功: {len(self.success_list)} 个\n\n")
            for item in self.success_list:
                f.write(f"ID {item['id']}: {item['name']}\n")
                f.write(f"  文件: {item['file']}\n")
                f.write(f"  URL: {item['url']}\n\n")

            if self.no_video_list:
                f.write(f"\n⚠️  无视频: {len(self.no_video_list)} 个\n")
                f.write(f"{', '.join(map(str, self.no_video_list))}\n")

            if self.failed_list:
                f.write(f"\n❌ 失败: {len(self.failed_list)} 个\n")
                f.write(f"{', '.join(map(str, self.failed_list))}\n")

        print(f"📄 报告已保存: {filename}")


# 使用示例
if __name__ == "__main__":
    downloader = VideoDownloader()

    # 批量下载
    downloader.batch_download(
        start_id=121260,
        end_id=121110,
        delay=2
    )

    # 重试失败的
    if downloader.failed_list:
        print("\n重试失败的下载? (y/n): ", end='')
        if input().lower() == 'y':
            downloader.retry_failed()

    # 保存报告
    downloader.save_report()
