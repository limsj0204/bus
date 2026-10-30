// 홈 화면 설치용 최소 서비스 워커. 아무것도 캐시하지 않아 항상 최신 목록을 보여준다.
self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", event => event.waitUntil(self.clients.claim()));
