<template>
  <div class="m-home">
    <div class="m-welcome">
      <div class="m-avatar">{{ user?.name?.[0] || 'T' }}</div>
      <div>
        <div class="m-name">{{ user?.name || '教师' }}</div>
        <div class="m-role">{{ isAdmin ? '管理员' : '班主任' }}</div>
      </div>
    </div>

    <van-grid :column-num="2" :gutter="12" class="m-grid">
      <van-grid-item icon="clock-o" text="考勤打卡" @click="$router.push('/m/checkin')" />
      <van-grid-item icon="friends-o" text="学生速查" @click="$router.push('/m/students')" />
      <van-grid-item icon="add-o" text="记表现" @click="$router.push('/m/record?type=performance')" />
      <van-grid-item icon="chat-o" text="记谈心" @click="$router.push('/m/record?type=talk')" />
      <van-grid-item icon="notes-o" text="请假管理" @click="$router.push('/m/leaves')" />
    </van-grid>
  </div>
</template>

<script setup>
import { getUser, isSchoolAdmin, isPlatformAdmin } from '../../utils/auth'

const user = getUser()
const isAdmin = isSchoolAdmin() || isPlatformAdmin()
</script>

<style scoped>
.m-home {
  padding: 16px;
}
.m-welcome {
  display: flex;
  align-items: center;
  gap: 12px;
  background: linear-gradient(135deg, #2563eb, #4f46e5);
  color: #fff;
  border-radius: 12px;
  padding: 20px 16px;
  margin-bottom: 16px;
}
.m-avatar {
  width: 48px;
  height: 48px;
  line-height: 48px;
  text-align: center;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.2);
  font-size: 20px;
  font-weight: 600;
}
.m-name {
  font-size: 17px;
  font-weight: 600;
}
.m-role {
  font-size: 12px;
  opacity: 0.85;
  margin-top: 2px;
}
.m-grid {
  background: #fff;
  border-radius: 12px;
  overflow: hidden;
}
.m-tip {
  margin-top: 16px;
  background: #fff7e6;
  border-radius: 8px;
  padding: 12px;
  font-size: 12px;
  color: #ad6800;
  line-height: 1.6;
}
.m-tip p {
  margin: 0;
}
</style>
