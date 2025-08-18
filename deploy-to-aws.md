# AWS EC2 배포 가이드

## 1. EC2 인스턴스 생성
```bash
# AWS CLI 설치 후
aws ec2 run-instances \
  --image-id ami-0c02fb55956c7d316 \
  --instance-type t3.medium \
  --key-name your-key-pair \
  --security-group-ids sg-xxxxxxxxx \
  --subnet-id subnet-xxxxxxxxx \
  --user-data file://user-data.sh
```

## 2. 서버 설정 스크립트 (user-data.sh)
```bash
#!/bin/bash
yum update -y
yum install -y docker git

# Docker 시작
systemctl start docker
systemctl enable docker
usermod -a -G docker ec2-user

# Docker Compose 설치
curl -L "https://github.com/docker/compose/releases/download/v2.20.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose

# 프로젝트 클론
cd /home/ec2-user
git clone https://github.com/your-username/reddit-ghost-publisher.git
cd reddit-ghost-publisher

# 환경 변수 설정
cp .env.production.example .env.production
# 실제 API 키들로 수정 필요

# 배포 실행
docker-compose -f docker-compose.prod.yml up -d
```

## 3. 보안 그룹 설정
- 포트 8000: API 서버
- 포트 5003: 어드민 API 서버
- 포트 22: SSH
- 포트 443: HTTPS (선택사항)

## 4. 도메인 연결
- Route 53에서 도메인 설정
- 예: api.your-domain.com → EC2 IP