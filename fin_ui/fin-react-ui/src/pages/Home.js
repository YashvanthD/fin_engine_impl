import React, { useEffect } from 'react';
import { Paper, Typography, Button, Grid, Card, CardContent, Stack, Dialog, DialogTitle, DialogContent, DialogActions, Select, MenuItem, FormControl, InputLabel } from '@mui/material';
import { useNavigate } from 'react-router-dom';
import { getRefreshToken } from '../utils/auth';

const mockStats = {
  activeTasks: 12,
  criticalTasks: 3
};

const mockAlerts = [
  {
    title: 'Sensor failure in Zone 2',
    description: 'Sensor in Zone 2 has stopped responding.',
    completeBy: 1764586198,
    unread: true,
    priority: 1
  },
  {
    title: 'Water quality threshold exceeded',
    description: 'Detected water quality above safe threshold.',
    completeBy: 1764590198,
    unread: false,
    priority: 2
  },
  {
    title: 'Sampling overdue in Zone 5',
    description: 'Sampling not completed for Zone 5.',
    completeBy: 1764594198,
    unread: true,
    priority: 3
  },
  {
    title: 'Transform maintenance required',
    description: 'Transform needs scheduled maintenance.',
    completeBy: 1764598198,
    unread: false,
    priority: 4
  },
  {
    title: 'New report available',
    description: 'A new system report is available for review.',
    completeBy: 1764602198,
    unread: true,
    priority: 5
  }
];

function formatTime(ts) {
  const date = new Date(ts * 1000);
  return date.toLocaleString();
}

const actions = [
  { label: 'Water Test', to: '/water-test' },
  { label: 'Sampling', to: '/sampling' },
  { label: 'Transform', to: '/transform' },
  { label: 'New Task', to: '/tasks/new' },
  { label: 'Reports', to: '/reports' }
];

function getPriorityStyle(priority) {
  switch (priority) {
    case 1:
      return { border: '1.5px solid #f44336', boxShadow: '0 0 4px #f44336' };
    case 2:
      return { border: '1.5px solid #ff7961', boxShadow: '0 0 4px #ff7961' };
    case 3:
      return { border: '1.5px solid #ff9800', boxShadow: '0 0 4px #ff9800' };
    case 4:
      return { border: '1.5px solid #ffeb3b', boxShadow: '0 0 4px #ffeb3b' };
    case 5:
      return { border: '1.5px solid #4caf50', boxShadow: '0 0 4px #4caf50' };
    default:
      return { border: '1px solid #e0e0e0' };
  }
}

export default function Home() {
  const navigate = useNavigate();
  const [dialogOpen, setDialogOpen] = React.useState(false);
  const [selectedAlert, setSelectedAlert] = React.useState(null);
  const [remindDropdown, setRemindDropdown] = React.useState('');
  const [alerts, setAlerts] = React.useState(mockAlerts);

  useEffect(() => {
    const refreshToken = getRefreshToken();
    if (!refreshToken) {
      console.log('[Home Debug] No refresh token found, redirecting to /login');
      navigate('/login');
    }
  }, [navigate]);

  // Dialog handlers
  const handleAlertClick = (alert, idx) => {
    // Mark as read on open
    const updatedAlerts = alerts.map((a, i) => i === idx ? { ...a, unread: false } : a);
    setAlerts(updatedAlerts);
    setSelectedAlert({ ...alert, idx });
    setDialogOpen(true);
    setRemindDropdown('');
    console.log('[Home Debug] Alert opened (marked as read):', alert.title);
  };
  const handleDialogClose = () => {
    setDialogOpen(false);
    setSelectedAlert(null);
    setRemindDropdown('');
  };
  const handleMarkAsDone = () => {
    if (selectedAlert) {
      const updatedAlerts = alerts.filter((_, i) => i !== selectedAlert.idx);
      setAlerts(updatedAlerts);
      setDialogOpen(false);
      setSelectedAlert(null);
      setRemindDropdown('');
      console.log('[Home Debug] Alert marked as done:', selectedAlert.title);
    }
  };
  const handleRemindMeLater = () => {
    if (selectedAlert && remindDropdown) {
      let addSeconds = 0;
      if (remindDropdown === '5min') addSeconds = 5 * 60;
      else if (remindDropdown === '30min') addSeconds = 30 * 60;
      else if (remindDropdown === '1hour') addSeconds = 60 * 60;
      else if (remindDropdown === 'custom') addSeconds = 2 * 60 * 60; // Example: 2 hours for custom
      const updatedAlerts = alerts.map((a, i) =>
        i === selectedAlert.idx ? { ...a, completeBy: a.completeBy + addSeconds } : a
      );
      setAlerts(updatedAlerts);
      setDialogOpen(false);
      setSelectedAlert(null);
      setRemindDropdown('');
      console.log('[Home Debug] Remind me later set for:', selectedAlert.title, remindDropdown);
    }
  };
  const handleMarkAsUnread = () => {
    if (selectedAlert) {
      const updatedAlerts = alerts.map((a, i) => i === selectedAlert.idx ? { ...a, unread: true } : a);
      setAlerts(updatedAlerts);
      setDialogOpen(false);
      setSelectedAlert(null);
      setRemindDropdown('');
      console.log('[Home Debug] Alert marked as unread:', selectedAlert.title);
    }
  };

  // Top summary: total critical actions and alerts in red alert note
  const totalCritical = mockStats.criticalTasks + mockAlerts.length;
  const renderCriticalSummary = (
    <Paper elevation={2} sx={{ mb: 4, p: 2, backgroundColor: '#ffebee', border: '1px solid #f44336' }}>
      <Typography variant="h6" color="error" sx={{ fontWeight: 'bold' }}>
        Critical: {mockStats.criticalTasks} actions & {mockAlerts.length} alerts
      </Typography>
      <Typography variant="body2" color="error">
        Immediate attention required for critical actions and alerts.
      </Typography>
    </Paper>
  );

  // Section 1: Task stats
  const renderTaskStats = (
    <Grid container spacing={2} sx={{ mb: 4 }}>
      <Grid item xs={12} sm={6}>
        <Card>
          <CardContent>
            <Typography variant="h6">Active Tasks</Typography>
            <Typography variant="h3" color="primary">{mockStats.activeTasks}</Typography>
          </CardContent>
        </Card>
      </Grid>
      <Grid item xs={12} sm={6}>
        <Card>
          <CardContent>
            <Typography variant="h6">Critical Tasks</Typography>
            <Typography variant="h3" color="error">{mockStats.criticalTasks}</Typography>
          </CardContent>
        </Card>
      </Grid>
    </Grid>
  );

  // Section 2: Top 5 Alerts
  const renderAlerts = (
    <Paper elevation={2} sx={{ mb: 4, p: 2 }}>
      <Typography variant="h6" sx={{ mb: 2 }}>Top 5 Alerts</Typography>
      <Grid container spacing={2}>
        {alerts.map((alert, idx) => (
          <Grid item xs={12} sm={6} md={4} key={idx}>
            <Card sx={{ cursor: 'pointer', ...getPriorityStyle(alert.priority) }} onClick={() => handleAlertClick(alert, idx)}>
              <CardContent>
                <Typography variant="body1" sx={{ fontWeight: alert.unread ? 'bold' : 'normal', color: alert.unread ? 'error.main' : 'inherit' }}>
                  {alert.title} <span style={{float:'right', fontWeight:'bold', color:'#888'}}>#{alert.priority}</span>
                </Typography>
                <Typography variant="body2" sx={{ mb: 1 }}>{alert.description}</Typography>
                <Typography variant="caption" color="text.secondary">Complete by: {formatTime(alert.completeBy)}</Typography>
              </CardContent>
            </Card>
          </Grid>
        ))}
      </Grid>
      <Stack direction="row" justifyContent="flex-end" sx={{ mt: 2 }}>
        <Button variant="outlined" onClick={() => { console.log('[Home Debug] See more alerts clicked'); navigate('/alerts'); }}>See More</Button>
      </Stack>
      <Dialog open={dialogOpen} onClose={handleDialogClose} maxWidth="sm" fullWidth>
        <DialogTitle>
          {selectedAlert?.title} <span style={{float:'right', fontWeight:'bold', color:'#888'}}>#{selectedAlert?.priority}</span>
        </DialogTitle>
        <DialogContent>
          <Typography variant="body2" sx={{ mb: 1 }}>{selectedAlert?.description}</Typography>
          <Typography variant="caption" color="text.secondary">Complete by: {selectedAlert ? formatTime(selectedAlert.completeBy) : ''}</Typography>
          {!selectedAlert?.unread && (
            <Typography variant="body2" color="success.main" sx={{ mt: 2 }}>This alert is read.</Typography>
          )}
          {selectedAlert?.unread && (
            <Typography variant="body2" color="error" sx={{ mt: 2 }}>This alert is unread.</Typography>
          )}
          <FormControl fullWidth sx={{ mt: 2 }}>
            <InputLabel id="remind-label">Remind Me Later</InputLabel>
            <Select
              labelId="remind-label"
              value={remindDropdown}
              label="Remind Me Later"
              onChange={e => setRemindDropdown(e.target.value)}
              variant="outlined"
            >
              <MenuItem value="5min">5 min</MenuItem>
              <MenuItem value="30min">30 min</MenuItem>
              <MenuItem value="1hour">1 hour</MenuItem>
              <MenuItem value="custom">Custom (2 hours)</MenuItem>
            </Select>
          </FormControl>
        </DialogContent>
        <DialogActions>
          <Button onClick={handleMarkAsDone} color="primary">Mark as Done</Button>
          <Button onClick={handleRemindMeLater} color="info" disabled={!remindDropdown}>Remind Me Later</Button>
          <Button onClick={handleMarkAsUnread} color="warning">Mark as Unread</Button>
          <Button onClick={handleDialogClose}>Close</Button>
        </DialogActions>
      </Dialog>
    </Paper>
  );

  // Section 3: Actions
  const renderActions = (
    <Paper elevation={2} sx={{ p: 2 }}>
      <Typography variant="h6" sx={{ mb: 2 }}>Actions</Typography>
      <Grid container spacing={2}>
        {actions.map((action) => (
          <Grid item xs={12} sm={6} md={4} key={action.label}>
            <Card sx={{ cursor: 'pointer' }} onClick={() => { console.log(`[Home Debug] Action clicked: ${action.label}`); navigate(action.to); }}>
              <CardContent>
                <Typography variant="body1">{action.label}</Typography>
              </CardContent>
            </Card>
          </Grid>
        ))}
      </Grid>
    </Paper>
  );

  return (
    <Paper elevation={3} sx={{padding:4, maxWidth:1200, margin:'40px auto'}}>
      {renderCriticalSummary}
      <Typography variant="h5" gutterBottom>Home Dashboard</Typography>
      {renderTaskStats}
      {renderAlerts}
      {renderActions}
    </Paper>
  );
}
