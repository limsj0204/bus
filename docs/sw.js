// 홈 화면 설치용 최소 서비스 워커. 캐시하지 않고 항상 네트워크에서 받아 최신 목록을 보여준다.
self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", event => event.waitUntil(self.clients.claim()));
self.addEventListener("fetch", () => {});
