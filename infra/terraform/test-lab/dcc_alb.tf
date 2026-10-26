resource "aws_lb" "dcc" {
  name               = "${var.name_prefix}-dcc-alb"
  internal           = false
  load_balancer_type = "application"
  ip_address_type    = "ipv4"
  subnets            = [for index in range(length(local.availability_zones)) : aws_subnet.public[tostring(index)].id]
  security_groups    = [aws_security_group.dcc_alb.id]

  tags = {
    Name    = "${var.name_prefix}-dcc-alb"
    Project = "DCC"
  }
}

resource "aws_lb_target_group" "dcc_app" {
  name        = "${var.name_prefix}-dcc-tg"
  port        = 8000
  protocol    = "HTTP"
  target_type = "ip"
  vpc_id      = aws_vpc.test_lab.id

  health_check {
    enabled             = true
    path                = "/api/health/"
    port                = "traffic-port"
    protocol            = "HTTP"
    matcher             = "200"
    healthy_threshold   = 3
    unhealthy_threshold = 3
    interval            = 30
    timeout             = 5
  }

  tags = {
    Name    = "${var.name_prefix}-dcc-tg"
    Project = "DCC"
  }
}

resource "aws_lb_listener" "dcc_http" {
  load_balancer_arn = aws_lb.dcc.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.dcc_app.arn
  }

  tags = {
    Name    = "${var.name_prefix}-dcc-http"
    Project = "DCC"
  }
}

resource "aws_lb_listener_rule" "dcc_host_rewrite" {
  listener_arn = aws_lb_listener.dcc_http.arn
  priority     = 1

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.dcc_app.arn
  }

  condition {
    path_pattern {
      values = ["/*"]
    }
  }

  transform {
    type = "host-header-rewrite"

    host_header_rewrite_config {
      rewrite {
        regex   = "^(.*)$"
        replace = "dcc-app.dcc-test.internal"
      }
    }
  }

  tags = {
    Name    = "${var.name_prefix}-dcc-host-rewrite"
    Project = "DCC"
  }
}
